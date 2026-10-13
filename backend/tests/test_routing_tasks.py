"""Department routing, priority/escalation policy, task lifecycle additions, duplicate prevention,
audit events and schema migrations."""
import sqlite3

import pytest
from sqlalchemy import create_engine, inspect, text

from database import AuditLog, Base, Ticket
from migrations import run_migrations
from models_care import AuditEvent
from routing import MAX_EMERGENCY_SLA_MINUTES, route_task
from tasks_service import create_ticket, dedupe_key

pytestmark = pytest.mark.real_auth


def intake(care, user, text, **extra):
    res = care.client.post("/api/calls/process-transcript", headers=user.headers,
                           json={"raw_transcript": text, "language": "en", **extra})
    assert res.status_code == 200, res.text
    return res.json()


def team_of(body, needle):
    return next(t["assigned_team"] for t in body["extracted_tickets"] if needle in (t["raw_quote"] + t["title"]).lower())


# ------------------------------------------------------------------ routing
def test_default_routing_sends_each_request_to_its_team_with_a_reason(care):
    nurse = care.make_user("nurse")
    body = intake(care, nurse, "Please send the billing statement for room 5. "
                               "The insurance claim pre-authorisation is pending. "
                               "Refill the prescription medicine for the patient.")
    teams = {t["assigned_team"] for t in body["extracted_tickets"]}
    assert {"Patient Billing & Accounts", "Health Insurance & Pre-Authorisation", "Pharmacy & Therapeutics"} <= teams
    for t in body["extracted_tickets"]:
        assert t["routing_reason"] and t["task_category"]
        assert any(a["action"] == "ROUTED" for a in t["audit_logs"])


def test_admin_rule_overrides_default_and_records_why(care):
    admin, nurse = care.make_user("admin"), care.make_user("nurse")
    rule = care.client.post("/api/routing/rules", headers=admin.headers, json={
        "name": "Billing to finance desk", "priority": 10, "match_category": "billing_inquiry",
        "target_team": "Finance Desk"}).json()
    body = intake(care, nurse, "Please send the billing statement for room 5.")
    t = body["extracted_tickets"][0]
    assert t["assigned_team"] == "Finance Desk" and t["department"] == "Finance Desk"
    assert f"rule #{rule['id']}" in t["routing_reason"]
    # deactivating the rule restores the default
    care.client.put(f"/api/routing/rules/{rule['id']}", headers=admin.headers, json={
        "name": "Billing to finance desk", "priority": 10, "match_category": "billing_inquiry",
        "target_team": "Finance Desk", "is_active": False})
    t2 = intake(care, nurse, "Please send the billing statement for room 6.")["extracted_tickets"][0]
    assert t2["assigned_team"] == "Patient Billing & Accounts"


def test_rule_priority_order_and_keyword_matching(care):
    admin, nurse = care.make_user("admin"), care.make_user("nurse")
    base = {"match_category": "billing_inquiry"}
    care.client.post("/api/routing/rules", headers=admin.headers,
                     json={"name": "late", "priority": 50, "target_team": "Team B", **base})
    care.client.post("/api/routing/rules", headers=admin.headers,
                     json={"name": "early", "priority": 5, "target_team": "Team A", **base})
    care.client.post("/api/routing/rules", headers=admin.headers,
                     json={"name": "kw", "priority": 1, "match_keyword": "refund", "target_team": "Refund Team"})
    assert intake(care, nurse, "Please send the billing statement.")["extracted_tickets"][0]["assigned_team"] == "Team A"
    assert intake(care, nurse, "The billing refund is delayed.")["extracted_tickets"][0]["assigned_team"] == "Refund Team"


def test_fallback_queue_when_nothing_matches(care):
    with care.Session() as db:
        decision = route_task(db, standard_category=None, task_category=None, urgency="ROUTINE", text="???")
        assert decision.fallback and decision.source == "fallback" and decision.team == "Triage Review Queue"
        assert "fallback queue" in decision.reason.lower()


def test_fallback_queue_is_configurable(care):
    admin = care.make_user("admin")
    care.client.put("/api/routing/policy", headers=admin.headers, json={"fallback_team": "Manual Triage Desk"})
    with care.Session() as db:
        assert route_task(db, standard_category=None, task_category=None, urgency="ROUTINE").team == "Manual Triage Desk"


def test_emergency_goes_straight_to_emergency_team_and_cannot_be_diverted(care):
    admin, nurse = care.make_user("admin"), care.make_user("nurse")
    care.client.post("/api/routing/rules", headers=admin.headers, json={
        "name": "send everything to billing", "priority": 1, "target_team": "Patient Billing & Accounts"})
    body = intake(care, nurse, "Patient Hari in room 3 has severe chest pain and cannot breathe!")
    stat = [t for t in body["extracted_tickets"] if t["urgency"] == "STAT_EMERGENCY"]
    assert body["emergency_detected"] and stat
    t = stat[0]
    assert t["assigned_team"] == "Rapid Response & Critical Nursing"
    assert "emergency_escalation_required" in t["clinical_flags"]
    assert "approved emergency escalation procedure" in t["escalation_reason"]
    assert any(a["action"] == "EMERGENCY_ESCALATION_FLAGGED" for a in t["audit_logs"])
    assert t["sla_minutes"] <= MAX_EMERGENCY_SLA_MINUTES


def test_admin_cannot_target_emergency_or_set_unsafe_emergency_sla(care):
    admin = care.make_user("admin")
    r = care.client.post("/api/routing/rules", headers=admin.headers, json={
        "name": "x", "target_team": "Y", "match_urgency": "STAT_EMERGENCY"})
    assert r.status_code == 422
    r = care.client.put("/api/routing/policy", headers=admin.headers, json={"sla_minutes": {"STAT_EMERGENCY": 120}})
    assert r.status_code == 422
    ok = care.client.put("/api/routing/policy", headers=admin.headers, json={"sla_minutes": {"URGENT": 30, "ROUTINE": 90}})
    assert ok.status_code == 200 and ok.json()["sla_minutes"]["URGENT"] == 30


def test_priority_policy_changes_sla_of_new_tasks(care):
    admin, nurse = care.make_user("admin"), care.make_user("nurse")
    care.client.put("/api/routing/policy", headers=admin.headers, json={"sla_minutes": {"INQUIRY": 15, "ROUTINE": 15, "URGENT": 15}})
    t = intake(care, nurse, "Room 4 would like some water please.")["extracted_tickets"][0]
    assert t["sla_minutes"] == 15


def test_negated_emergency_terms_are_not_escalated(care):
    nurse = care.make_user("nurse")
    body = intake(care, nurse, "Patient Uma in room 2 has no chest pain, just needs her dressing changed.")
    assert not body["emergency_detected"]


# ------------------------------------------------------------------ tasks
def test_multiple_tasks_one_conversation_all_linked(care):
    nurse = care.make_user("nurse")
    body = intake(care, nurse, "Patient Anil needs a nurse to check the drip. Please send his billing statement. "
                               "Also reschedule his appointment.")
    assert len(body["extracted_tickets"]) >= 3
    assert {t["call_id"] for t in body["extracted_tickets"]} == {body["call"]["id"]}


def test_extended_statuses_and_validation(care):
    nurse = care.make_user("nurse")
    tid = intake(care, nurse, "Room 4 needs water.")["extracted_tickets"][0]["id"]
    for status in ("AWAITING_REVIEW", "ASSIGNED", "AWAITING_PATIENT", "AWAITING_EXTERNAL", "IN_PROGRESS"):
        r = care.client.patch(f"/api/tickets/{tid}", headers=nurse.headers, json={"status": status})
        assert r.status_code == 200 and r.json()["status"] == status
    assert care.client.patch(f"/api/tickets/{tid}", headers=nurse.headers, json={"status": "BANANA"}).status_code == 400
    closed = care.client.patch(f"/api/tickets/{tid}", headers=nurse.headers,
                               json={"status": "CLOSED", "resolution_notes": "Done"}).json()
    assert closed["status"] == "CLOSED" and closed["resolved_at"] and closed["resolution_notes"] == "Done"


def test_reassignment_is_audited_with_real_identity(care):
    nurse = care.make_user("nurse", full_name="Nurse Asha")
    tid = intake(care, nurse, "Room 4 needs water.")["extracted_tickets"][0]["id"]
    r = care.client.post(f"/api/tickets/{tid}/assign", headers=nurse.headers,
                         json={"assigned_team": "Facilities & Environmental Services", "assigned_staff": "Ravi"})
    logs = r.json()["audit_logs"]
    assigned = next(a for a in logs if a["action"] == "ASSIGNED")
    assert assigned["actor"] == "Nurse Asha" and "Facilities" in assigned["note"]


def test_task_filters_search_and_pagination(care):
    nurse = care.make_user("nurse")
    p = care.make_patient("Filter Person")
    intake(care, nurse, "Please send the billing statement.", patient_id=p.id)
    intake(care, nurse, "Room 4 needs water. Also the insurance claim is pending.")
    allr = care.client.get("/api/tickets", headers=nurse.headers)
    total = int(allr.headers["X-Total-Count"])
    assert total == len(allr.json()) >= 3
    page = care.client.get("/api/tickets?limit=2&offset=0", headers=nurse.headers)
    assert len(page.json()) == 2 and int(page.headers["X-Total-Count"]) == total
    by_cat = care.client.get("/api/tickets?task_category=billing_inquiry", headers=nurse.headers).json()
    assert by_cat and all(t["task_category"] == "billing_inquiry" for t in by_cat)
    by_patient = care.client.get(f"/api/tickets?patient_id={p.id}", headers=nurse.headers).json()
    assert by_patient and all(t["patient_id"] == p.id for t in by_patient)


def test_overdue_tasks_are_identified(care):
    from datetime import datetime, timedelta, timezone
    nurse = care.make_user("nurse")
    tid = intake(care, nurse, "Room 4 needs water.")["extracted_tickets"][0]["id"]
    with care.Session() as db:
        t = db.get(Ticket, tid)
        t.deadline_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    overdue = care.client.get("/api/tickets?is_overdue=true", headers=nurse.headers).json()
    assert [t["id"] for t in overdue] == [tid]
    care.client.patch(f"/api/tickets/{tid}", headers=nurse.headers, json={"status": "CLOSED"})
    assert care.client.get("/api/tickets?is_overdue=true", headers=nurse.headers).json() == []


# ------------------------------------------------------------------ duplicate prevention
def test_identical_task_cannot_be_inserted_twice_for_a_conversation(care):
    nurse = care.make_user("nurse")
    body = intake(care, nurse, "Room 4 needs water.")
    call_id = body["call"]["id"]
    draft = {"category": "Food, dietary and nutrition requests", "urgency": "ROUTINE", "title": "Water",
             "description": "d", "raw_quote": "Room 4 needs water."}
    with care.Session() as db:
        first = create_ticket(db, draft, call_id=call_id, patient_id=None, actor="t", source_note="n")
        db.commit()
        second = create_ticket(db, draft, call_id=call_id, patient_id=None, actor="t", source_note="n")
        db.commit()
        assert first is not None and second is None
        assert db.query(Ticket).filter(Ticket.call_id == call_id, Ticket.dedupe_key == dedupe_key(call_id, draft)).count() == 1


def test_database_blocks_duplicate_even_if_application_check_is_bypassed(care):
    nurse = care.make_user("nurse")
    call_id = intake(care, nurse, "Room 4 needs water.")["call"]["id"]
    from sqlalchemy.exc import IntegrityError
    with care.Session() as db:
        existing = db.query(Ticket).filter(Ticket.call_id == call_id).first()
        clone = Ticket(call_id=call_id, department="x", title="x", description="x", urgency="ROUTINE",
                       dedupe_key=existing.dedupe_key)
        db.add(clone)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_resubmitting_the_same_conversation_is_idempotent(care):
    nurse = care.make_user("nurse")
    payload = {"raw_transcript": "Room 4 needs water.", "language": "en", "idempotency_key": "retry-1"}
    a = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json=payload).json()
    b = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json=payload).json()
    assert a["call"]["id"] == b["call"]["id"]
    assert len(care.client.get("/api/tickets", headers=nurse.headers).json()) == len(a["extracted_tickets"])


# ------------------------------------------------------------------ audit trail
def test_sensitive_actions_write_global_audit_events(care):
    nurse, admin = care.make_user("nurse"), care.make_user("admin")
    p = care.make_patient("Audit Patient")
    body = intake(care, nurse, "Room 4 needs water.", patient_id=p.id)
    tid = body["extracted_tickets"][0]["id"]
    care.client.get(f"/api/tickets/{tid}", headers=nurse.headers)
    care.client.patch(f"/api/tickets/{tid}", headers=nurse.headers, json={"status": "IN_PROGRESS"})
    care.client.get(f"/api/patients/{p.id}", headers=nurse.headers)
    events = care.client.get("/api/audit/events?page_size=200", headers=admin.headers).json()["items"]
    actions = {e["action"] for e in events}
    assert {"conversation_created", "task_viewed", "task_updated", "patient_viewed"} <= actions
    mine = [e for e in events if e["action"] == "patient_viewed"][0]
    assert mine["actor_user_id"] == nurse.id and mine["patient_id"] == p.id
    assert care.client.get("/api/audit/verify", headers=admin.headers).json()["intact"] is True
    scoped = care.client.get(f"/api/audit/events?patient_id={p.id}", headers=admin.headers).json()
    assert scoped["total"] >= 3


def test_error_responses_do_not_leak_internals(care, monkeypatch):
    nurse = care.make_user("nurse")
    import main

    def explode(*a, **k):
        raise RuntimeError("secret patient detail: John Doe has HIV")

    monkeypatch.setattr(main, "create_ticket", explode)
    res = care.client.post("/api/calls/process-transcript", headers=nurse.headers,
                           json={"raw_transcript": "Room 4 needs water.", "language": "en"})
    assert res.status_code == 500 and "John Doe" not in res.text and "Nothing was saved" in res.text
    assert care.client.get("/api/calls", headers=nurse.headers).json() == []     # transaction rolled back


# ------------------------------------------------------------------ migrations
def test_migration_upgrades_a_pre_existing_database_without_losing_rows(tmp_path):
    path = tmp_path / "legacy.db"
    raw = sqlite3.connect(path)
    raw.executescript("""
        CREATE TABLE calls (id INTEGER PRIMARY KEY, raw_transcript TEXT NOT NULL);
        CREATE TABLE tickets (id INTEGER PRIMARY KEY, call_id INTEGER, department VARCHAR(100) NOT NULL,
                              title VARCHAR(200) NOT NULL, description TEXT NOT NULL, urgency VARCHAR(50) NOT NULL);
        INSERT INTO calls (id, raw_transcript) VALUES (1, 'legacy call');
        INSERT INTO tickets (id, call_id, department, title, description, urgency)
            VALUES (1, 1, 'Nursing & Clinical Care', 'Legacy task', 'old', 'ROUTINE');
    """)
    raw.commit()
    raw.close()

    engine = create_engine(f"sqlite:///{path}")
    import models_care  # noqa: F401
    Base.metadata.create_all(bind=engine)       # creates only the missing (new) tables
    assert run_migrations(engine) == [2, 3]
    insp = inspect(engine)
    assert {"patient_id", "extraction_json", "original_asr_transcript"} <= {c["name"] for c in insp.get_columns("calls")}
    assert {"patient_id", "task_category", "routing_reason", "dedupe_key"} <= {c["name"] for c in insp.get_columns("tickets")}
    assert run_migrations(engine) == []         # idempotent
    with engine.connect() as conn:
        assert conn.execute(text("SELECT raw_transcript FROM calls WHERE id=1")).scalar() == "legacy call"
        assert conn.execute(text("SELECT title FROM tickets WHERE id=1")).scalar() == "Legacy task"
        versions = [r[0] for r in conn.execute(text("SELECT version FROM schema_migrations ORDER BY version"))]
        assert versions == [2, 3]
    engine.dispose()
