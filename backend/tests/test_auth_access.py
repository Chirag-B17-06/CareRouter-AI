"""Authentication, role-based access, department scoping, rate limiting and audit of denials."""
import pytest

import ratelimit
from audit import verify_chain
from models_care import AuditEvent, User

pytestmark = pytest.mark.real_auth

STAFF_ENDPOINTS = [
    ("get", "/api/tickets"), ("get", "/api/calls"), ("get", "/api/patients"),
    ("get", "/api/analytics"), ("get", "/api/scheduling/overview"), ("get", "/api/audit/events"),
]


def login(client, username, password="Str0ng-Passw0rd!"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_every_protected_endpoint_requires_a_token(care):
    for method, path in STAFF_ENDPOINTS:
        res = getattr(care.client, method)(path)
        assert res.status_code == 401, path
    assert care.client.post("/api/calls/process-transcript", json={"raw_transcript": "x"}).status_code == 401
    assert care.client.post("/api/audio/jobs").status_code == 401
    # health stays public and exposes no patient data
    assert care.client.get("/api/health").status_code == 200


def test_login_returns_token_and_permissions(care):
    care.make_user("nurse", username="nurse.a")
    res = login(care.client, "nurse.a")
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["role"] == "nurse"
    assert "audio:transcribe" in body["user"]["permissions"]
    me = care.client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["username"] == "nurse.a"


def test_bad_credentials_are_generic_and_audited(care):
    care.make_user("nurse", username="nurse.b")
    wrong_pw = login(care.client, "nurse.b", "wrong-password-123")
    unknown = login(care.client, "nobody", "whatever-password-1")
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json()["detail"] == unknown.json()["detail"]   # no user enumeration
    with care.Session() as db:
        assert db.query(AuditEvent).filter(AuditEvent.action == "login_failed").count() == 2


def test_account_locks_after_repeated_failures(care, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_FAILURES", "3")
    care.make_user("nurse", username="nurse.c")
    for _ in range(3):
        assert login(care.client, "nurse.c", "wrong-password-123").status_code == 401
    locked = login(care.client, "nurse.c")           # correct password, but locked
    assert locked.status_code == 429


def test_logout_revokes_existing_tokens(care):
    u = care.make_user("nurse")
    assert care.client.get("/api/tickets", headers=u.headers).status_code == 200
    assert care.client.post("/api/auth/logout", headers=u.headers).status_code == 200
    assert care.client.get("/api/tickets", headers=u.headers).status_code == 401


def test_tampered_or_garbage_token_rejected(care):
    u = care.make_user("nurse")
    bad = {"Authorization": u.headers["Authorization"][:-3] + "abc"}
    assert care.client.get("/api/tickets", headers=bad).status_code == 401
    assert care.client.get("/api/tickets", headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401


def test_deactivated_user_loses_access(care):
    admin = care.make_user("admin")
    nurse = care.make_user("nurse")
    assert care.client.post(f"/api/auth/users/{nurse.id}/deactivate", headers=admin.headers).status_code == 200
    assert care.client.get("/api/tickets", headers=nurse.headers).status_code == 401


def test_role_permissions_are_enforced_server_side(care):
    nurse = care.make_user("nurse")
    coordinator = care.make_user("coordinator", department="Patient Billing & Accounts")
    admin = care.make_user("admin")
    # only admins manage users / read audit / change routing
    assert care.client.get("/api/auth/users", headers=nurse.headers).status_code == 403
    assert care.client.get("/api/audit/events", headers=nurse.headers).status_code == 403
    rule = {"name": "x", "target_team": "Y", "priority": 5}
    assert care.client.post("/api/routing/rules", json=rule, headers=nurse.headers).status_code == 403
    assert care.client.post("/api/routing/rules", json=rule, headers=admin.headers).status_code == 201
    # coordinators cannot record audio or clinical data
    assert care.client.post("/api/audio/jobs", headers=coordinator.headers).status_code == 403
    p = care.make_patient("Fictional Person")
    assert care.client.get(f"/api/patients/{p.id}/clinical", headers=coordinator.headers).status_code == 403
    assert care.client.get(f"/api/patients/{p.id}/medications", headers=coordinator.headers).status_code == 403
    # denied attempts are audited
    with care.Session() as db:
        denied = db.query(AuditEvent).filter(AuditEvent.outcome == "denied", AuditEvent.action == "access_denied").count()
        assert denied >= 4


def test_patient_accounts_cannot_use_staff_apis(care):
    p = care.make_patient("Portal Patient")
    pu = care.make_user("patient", patient=p)
    for method, path in STAFF_ENDPOINTS:
        assert getattr(care.client, method)(path, headers=pu.headers).status_code == 403, path


def test_department_scoped_staff_only_see_their_queue(care):
    nurse = care.make_user("nurse")
    billing = care.make_user("coordinator", department="Patient Billing & Accounts")
    pharmacy = care.make_user("pharmacist", department="Pharmacy & Therapeutics")
    unscoped = care.make_user("coordinator")           # no department -> sees nothing
    res = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": "Please send the billing statement for room 12. Also the pharmacy must refill the prescription.",
        "language": "en"})
    assert res.status_code == 200, res.text
    teams = {t["assigned_team"] for t in res.json()["extracted_tickets"]}
    assert {"Patient Billing & Accounts", "Pharmacy & Therapeutics"} <= teams

    seen_billing = care.client.get("/api/tickets", headers=billing.headers).json()
    assert seen_billing and all(t["assigned_team"] == "Patient Billing & Accounts" for t in seen_billing)
    seen_pharm = care.client.get("/api/tickets", headers=pharmacy.headers).json()
    assert seen_pharm and all(t["assigned_team"] == "Pharmacy & Therapeutics" for t in seen_pharm)
    assert care.client.get("/api/tickets", headers=unscoped.headers).json() == []

    other_team_ticket = next(t for t in res.json()["extracted_tickets"] if t["assigned_team"] == "Pharmacy & Therapeutics")
    assert care.client.get(f"/api/tickets/{other_team_ticket['id']}", headers=billing.headers).status_code == 404
    assert care.client.patch(f"/api/tickets/{other_team_ticket['id']}", headers=billing.headers,
                             json={"status": "IN_PROGRESS"}).status_code == 404


def test_actor_identity_comes_from_session_not_request(care):
    nurse = care.make_user("nurse", full_name="Nurse Real Name")
    res = care.client.post("/api/calls/process-transcript", headers=nurse.headers,
                           json={"raw_transcript": "Room 4 needs an extra blanket.", "language": "en"})
    tid = res.json()["extracted_tickets"][0]["id"]
    ack = care.client.post(f"/api/tickets/{tid}/acknowledge", headers=nurse.headers,
                           json={"acknowledged_by": "Somebody Else"})
    assert ack.json()["acknowledged_by"] == "Nurse Real Name"


def test_rate_limit_returns_429(care, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    ratelimit.reset()
    codes = [care.client.get("/api/tickets").status_code for _ in range(8)]
    assert 429 in codes
    assert care.client.get("/api/health").status_code == 200   # health is exempt
    ratelimit.reset()


def test_password_policy_and_hashing(care):
    admin = care.make_user("admin")
    weak = care.client.post("/api/auth/users", headers=admin.headers, json={
        "username": "weak.user", "password": "short", "full_name": "Weak", "role": "nurse"})
    assert weak.status_code == 400
    ok = care.client.post("/api/auth/users", headers=admin.headers, json={
        "username": "good.user", "password": "Another-Str0ng-Pass", "full_name": "Good", "role": "nurse"})
    assert ok.status_code == 201
    with care.Session() as db:
        stored = db.query(User).filter(User.username == "good.user").one().password_hash
        assert stored.startswith("scrypt$") and "Another-Str0ng-Pass" not in stored


def test_audit_chain_detects_tampering(care):
    nurse = care.make_user("nurse")
    care.client.get("/api/tickets", headers=nurse.headers)
    care.client.post("/api/calls/process-transcript", headers=nurse.headers,
                     json={"raw_transcript": "Room 9 water please.", "language": "en"})
    with care.Session() as db:
        ok, broken = verify_chain(db)
        assert ok and broken is None
        ev = db.query(AuditEvent).filter(AuditEvent.action == "conversation_created").one()
        ev.outcome = "denied"          # simulate someone editing history
        db.commit()
        ok, broken = verify_chain(db)
        assert not ok and broken == ev.id


def test_audit_detail_never_stores_free_text_phi(care):
    from audit import record_audit
    with care.Session() as db:
        record_audit(db, user=None, action="x", resource_type="t", detail={
            "transcript": "patient has chest pain", "name": "Jane Doe", "count": 3, "phone": "9876543210"})
        db.commit()
        row = db.query(AuditEvent).filter(AuditEvent.action == "x").one()
        assert "chest pain" not in row.detail and "Jane" not in row.detail and "9876543210" not in row.detail
        assert '"count":3' in row.detail
