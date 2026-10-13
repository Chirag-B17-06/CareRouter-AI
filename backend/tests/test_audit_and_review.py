import pytest
import os
import sys
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import Base, get_db, Ticket, Call, AuditLog
from main import app

# In-memory test SQLite with StaticPool
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_database():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.pop(get_db, None)

client = TestClient(app)

def test_audit_log_created_on_transcript_intake():
    payload = {
        "caller_name": "Nurse Sunita",
        "patient_name": "Ramesh Kumar",
        "room_number": "402",
        "raw_transcript": "Patient in room 402 has scheduled physical therapy at 3 PM and wants evening soup.",
        "language": "en"
    }
    res = client.post("/api/calls/process-transcript", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["extracted_tickets"]) >= 1

    ticket_id = data["extracted_tickets"][0]["id"]
    t_res = client.get(f"/api/tickets/{ticket_id}")
    assert t_res.status_code == 200
    ticket_data = t_res.json()
    
    assert len(ticket_data["audit_logs"]) >= 1
    actions = [a["action"] for a in ticket_data["audit_logs"]]
    assert "CREATED" in actions
    created_audit = next(a for a in ticket_data["audit_logs"] if a["action"] == "CREATED")
    assert created_audit["actor"] == "AI Dispatch Engine"

def test_audit_log_flagged_for_review_on_uncertain_emergency():
    payload = {
        "caller_name": "Attendant",
        "patient_name": "Lakshmi Devi",
        "room_number": "ICU-2",
        "raw_transcript": "Not sure if patient Lakshmi in ICU-2 is having a heart attack or severe gas, she is sweating profusely.",
        "language": "en"
    }
    res = client.post("/api/calls/process-transcript", json=payload)
    assert res.status_code == 200
    data = res.json()
    
    flagged_ticket = next((t for t in data["extracted_tickets"] if t["requires_human_review"]), None)
    assert flagged_ticket is not None
    assert flagged_ticket["is_reviewed"] is False

    # Verify FLAGGED_FOR_REVIEW audit log exists
    actions = [a["action"] for a in flagged_ticket["audit_logs"]]
    assert "FLAGGED_FOR_REVIEW" in actions
    flag_audit = next(a for a in flagged_ticket["audit_logs"] if a["action"] == "FLAGGED_FOR_REVIEW")
    assert flag_audit["actor"] == "AI Safety Guard"

def test_audit_log_tracks_complete_lifecycle():
    payload = {
        "caller_name": "Ward Staff",
        "patient_name": "Vikram Singh",
        "room_number": "205",
        "raw_transcript": "Room 205 saline line needs changing within 1 hour.",
        "language": "en"
    }
    res = client.post("/api/calls/process-transcript", json=payload)
    assert res.status_code == 200
    ticket_id = res.json()["extracted_tickets"][0]["id"]

    # 1. Acknowledge
    ack_res = client.post(f"/api/tickets/{ticket_id}/acknowledge", json={"acknowledged_by": "Nurse Priya"})
    assert ack_res.status_code == 200

    # 2. Reassign
    assign_res = client.post(f"/api/tickets/{ticket_id}/assign", json={
        "assigned_staff": "Nurse John",
        "assigned_team": "Nursing & Clinical Care",
        "assigner": "Charge Nurse Deepa"
    })
    assert assign_res.status_code == 200

    # 3. Escalate
    esc_res = client.post(f"/api/tickets/{ticket_id}/escalate", json={
        "escalation_reason": "IV line blockage observed, requires cannulation senior",
        "escalated_by": "Nurse John"
    })
    assert esc_res.status_code == 200

    # 4. Add Clinical Note
    note_res = client.post(f"/api/tickets/{ticket_id}/notes", json={
        "note": "Line patent after flush.",
        "author": "Senior Nurse Meera"
    })
    assert note_res.status_code == 200

    # 5. Resolve
    resolve_res = client.post(f"/api/tickets/{ticket_id}/resolve", json={
        "resolved_by": "Nurse John",
        "resolution_notes": "Re-cannulation completed successfully, running smoothly."
    })
    assert resolve_res.status_code == 200

    # Inspect all audit logs
    final_ticket = client.get(f"/api/tickets/{ticket_id}").json()
    actions = [a["action"] for a in final_ticket["audit_logs"]]
    assert "CREATED" in actions
    assert "ACKNOWLEDGED" in actions
    assert "ASSIGNED" in actions
    assert "ESCALATED" in actions
    assert "NOTE_ADDED" in actions
    assert "RESOLVED" in actions

    actors = [a["actor"] for a in final_ticket["audit_logs"]]
    # Actor identity now comes from the authenticated session, not from client-supplied names.
    assert "Test Administrator" in actors
    assert "AI Dispatch Engine" in actors

def test_human_review_mode_approval():
    db = TestingSessionLocal()
    ticket = Ticket(
        department="Nursing & Clinical Care",
        title="Uncertain Breathlessness Query",
        description="Caller reports mild breathing trouble not sure if anxiety.",
        raw_quote="mild breathing trouble",
        urgency="URGENT",
        status="PENDING",
        requires_human_review=True,
        human_review_reason="Borderline respiratory clinical uncertainty",
        is_reviewed=False,
        room_number="112",
        patient_name="Ananya Roy"
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    ticket_id = ticket.id
    db.close()

    # Review with APPROVE action
    review_payload = {
        "reviewer_name": "Dr. Sandeep Rao",
        "action": "APPROVE",
        "review_notes": "Reviewed vital signs telemetry. Anxiety-related hyperventilation, urgent nursing reassurance appropriate."
    }
    res = client.post(f"/api/tickets/{ticket_id}/review", json=review_payload)
    assert res.status_code == 200
    data = res.json()

    assert data["is_reviewed"] is True
    assert data["requires_human_review"] is False
    assert data["reviewed_by"] == "Test Administrator"
    assert "telemetry" in data["review_notes"]

    # Verify audit log
    actions = [a["action"] for a in data["audit_logs"]]
    assert "HUMAN_REVIEW_APPROVED" in actions
    approve_audit = next(a for a in data["audit_logs"] if a["action"] == "HUMAN_REVIEW_APPROVED")
    assert approve_audit["actor"] == "Test Administrator"

def test_human_review_mode_correction_recalculates_sla():
    db = TestingSessionLocal()
    ticket = Ticket(
        department="Hospital Information & Patient Helpdesk",
        title="Vague Chest Tightness",
        description="Patient mentions uncomfortable heaviness in chest.",
        raw_quote="uncomfortable heaviness in chest",
        urgency="ROUTINE",
        sla_minutes=120,
        deadline_at=datetime.now(timezone.utc) + timedelta(minutes=120),
        status="PENDING",
        requires_human_review=True,
        human_review_reason="Vague description of possible cardiac discomfort",
        is_reviewed=False,
        room_number="308",
        patient_name="Suresh Verma"
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    ticket_id = ticket.id
    db.close()

    # Review with CORRECT action: upgrade to STAT_EMERGENCY and Rapid Response
    review_payload = {
        "reviewer_name": "Dr. Kavita Joshi (Cardiologist)",
        "action": "CORRECT",
        "corrected_urgency": "STAT_EMERGENCY",
        "corrected_department": "Rapid Response & Critical Nursing",
        "corrected_title": "Acute Angina / Rule out ACS",
        "corrected_action": "Immediate 12-lead ECG, troponin I stat, oxygen support",
        "review_notes": "High cardiac risk profile. Rerouted to Rapid Response immediately."
    }
    res = client.post(f"/api/tickets/{ticket_id}/review", json=review_payload)
    assert res.status_code == 200
    data = res.json()

    assert data["is_reviewed"] is True
    assert data["requires_human_review"] is False
    assert data["urgency"] == "STAT_EMERGENCY"
    assert data["sla_minutes"] == 5
    assert data["department"] == "Rapid Response & Critical Nursing"
    assert data["title"] == "Acute Angina / Rule out ACS"
    assert "ECG" in data["required_action"]

    # Verify audit log
    actions = [a["action"] for a in data["audit_logs"]]
    assert "HUMAN_REVIEW_CORRECTED" in actions
    corr_audit = next(a for a in data["audit_logs"] if a["action"] == "HUMAN_REVIEW_CORRECTED")
    assert corr_audit["actor"] == "Test Administrator"

def test_query_tickets_by_review_status():
    db = TestingSessionLocal()
    t_flagged = Ticket(
        department="Nursing",
        title="Flagged Unreviewed",
        description="Uncertain symptom",
        urgency="URGENT",
        status="PENDING",
        requires_human_review=True,
        is_reviewed=False
    )
    t_cleared = Ticket(
        department="Nursing",
        title="Reviewed Cleared",
        description="Clinically verified",
        urgency="ROUTINE",
        status="IN_PROGRESS",
        requires_human_review=False,
        is_reviewed=True
    )
    db.add_all([t_flagged, t_cleared])
    db.commit()
    db.refresh(t_flagged)
    db.refresh(t_cleared)
    flagged_id = t_flagged.id
    cleared_id = t_cleared.id
    db.close()

    # Query for unreviewed flagged tickets
    res = client.get("/api/tickets?requires_human_review=true&is_reviewed=false")
    assert res.status_code == 200
    items = res.json()
    assert any(t["id"] == flagged_id for t in items)
    assert not any(t["id"] == cleared_id for t in items)

def test_shift_handover_report_endpoint():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    t_stat = Ticket(
        department="Rapid Response & Critical Nursing",
        title="Code Blue Bed 4",
        description="Cardiac arrest crash team summoned",
        urgency="STAT_EMERGENCY",
        status="IN_PROGRESS",
        room_number="ICU-4",
        patient_name="Govind Rao",
        created_at=now - timedelta(hours=1)
    )
    t_overdue = Ticket(
        department="Pharmacy & Therapeutics",
        title="Critical Antibiotic Due",
        description="IV Meropenem stat",
        urgency="URGENT",
        sla_minutes=20,
        deadline_at=now - timedelta(minutes=15),
        status="PENDING",
        room_number="312",
        patient_name="Pooja Sen",
        created_at=now - timedelta(hours=2)
    )
    db.add_all([t_stat, t_overdue])
    db.commit()
    db.close()

    res = client.get("/api/reports/shift-handover?shift_hours=8&shift_lead=Nurse+In-Charge+Sunita")
    assert res.status_code == 200
    report = res.json()

    assert report["shift_hours"] == 8
    assert report["shift_lead"] == "Nurse In-Charge Sunita"
    assert report["active_tickets"] >= 2
    assert report["stat_emergency_count"] >= 1
    assert report["overdue_tickets_count"] >= 1
    assert len(report["departments"]) >= 2
    assert "CLINICAL SHIFT HANDOVER REPORT" in report["handover_briefing_markdown"]
    assert "Code Blue Bed 4" in report["handover_briefing_markdown"]

def test_export_tickets_json_and_csv():
    db = TestingSessionLocal()
    ticket = Ticket(
        department="Patient Billing & Accounts",
        title="Discharge Bill Clearance",
        description="Patient family requested itemized pharmacy invoice",
        urgency="INQUIRY",
        status="RESOLVED",
        room_number="501",
        patient_name="Manoj Nair",
        resolution_notes="Invoice audited and handed over to family."
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    ticket_id = ticket.id
    db.close()

    # Test JSON export
    res_json = client.get("/api/export/tickets?format=json")
    assert res_json.status_code == 200
    assert isinstance(res_json.json(), list)
    assert any(t["id"] == ticket_id for t in res_json.json())

    # Test CSV export
    res_csv = client.get("/api/export/tickets?format=csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "attachment; filename=" in res_csv.headers["content-disposition"]
    
    csv_text = res_csv.text
    assert "ID,Created At (UTC),Patient Name,Room Number,Department" in csv_text
    assert "Manoj Nair" in csv_text
    assert "Discharge Bill Clearance" in csv_text

def test_analytics_includes_unreviewed_count():
    db = TestingSessionLocal()
    ticket = Ticket(
        department="Nursing",
        title="Flagged Intake",
        description="Needs checking",
        urgency="URGENT",
        status="PENDING",
        requires_human_review=True,
        is_reviewed=False
    )
    db.add(ticket)
    db.commit()
    db.close()

    res = client.get("/api/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "unreviewed_tickets" in data
    assert data["unreviewed_tickets"] >= 1
