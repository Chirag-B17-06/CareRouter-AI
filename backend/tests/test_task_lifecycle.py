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
from main import app, calculate_sla_and_deadline

# In-memory test SQLite
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

def test_sla_deadline_calculation_helper():
    """Verify SLA calculation produces expected minutes and future deadline."""
    now = datetime.now(timezone.utc)
    stat_mins, stat_dl = calculate_sla_and_deadline("STAT_EMERGENCY", created_at=now)
    assert stat_mins == 5
    assert stat_dl > now

    urgent_mins, urgent_dl = calculate_sla_and_deadline("URGENT", created_at=now)
    assert urgent_mins == 20
    assert urgent_dl > now

    routine_mins, routine_dl = calculate_sla_and_deadline("ROUTINE", created_at=now)
    assert routine_mins == 120

    inquiry_mins, inquiry_dl = calculate_sla_and_deadline("INQUIRY", created_at=now)
    assert inquiry_mins == 240

    # Explicit deadline override
    exp_mins, exp_dl = calculate_sla_and_deadline("ROUTINE", explicit_deadline="within 30 minutes", created_at=now)
    assert exp_mins == 30

def test_process_transcript_sets_phase5_attributes():
    """Processing a real transcript automatically creates SLA, deadline, and assignment fields."""
    payload = {
        "caller_name": "Nurse Kelly",
        "patient_name": "George Brown",
        "room_number": "Room 402",
        "raw_transcript": "Patient in Room 402 has severe chest pain and cannot breathe!",
        "language": "en"
    }
    resp = client.post("/api/calls/process-transcript", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    tickets = data["extracted_tickets"]
    assert len(tickets) >= 1
    t = tickets[0]

    assert t["urgency"] == "STAT_EMERGENCY"
    assert t["sla_minutes"] == 5
    assert t["deadline_at"] is not None
    assert t["is_overdue"] is False
    assert t["is_acknowledged"] is False
    assert t["escalation_level"] == 0
    assert t["assigned_team"] != ""
    assert t["assigned_staff"] == "Unassigned"

def test_acknowledgement_lifecycle_transitions_status():
    """Acknowledging an unacknowledged PENDING task transitions it to IN_PROGRESS and logs timestamp."""
    payload = {
        "caller_name": "Nurse Kelly",
        "patient_name": "George Brown",
        "room_number": "Room 402",
        "raw_transcript": "Patient in Room 402 has severe chest pain and cannot breathe!",
        "language": "en"
    }
    create_resp = client.post("/api/calls/process-transcript", json=payload)
    t_id = create_resp.json()["extracted_tickets"][0]["id"]

    ack_resp = client.post(f"/api/tickets/{t_id}/acknowledge", json={"acknowledged_by": "Rapid Response Nurse Dave"})
    assert ack_resp.status_code == 200
    ack_data = ack_resp.json()

    assert ack_data["is_acknowledged"] is True
    assert ack_data["acknowledged_by"] == "Test Administrator"
    assert ack_data["acknowledged_at"] is not None
    assert ack_data["status"] == "IN_PROGRESS"

    # Verify audit log
    logs = ack_data["audit_logs"]
    assert any("ACKNOWLEDGED" in l["action"] for l in logs)

def test_staff_and_team_reassignment():
    """Assigning staff and team updates task fields and creates audit record."""
    payload = {
        "caller_name": "Unit Clerk",
        "patient_name": "Martha Stewart",
        "room_number": "Room 210",
        "raw_transcript": "Martha in Room 210 needs fresh water and a blanket.",
        "language": "en"
    }
    create_resp = client.post("/api/calls/process-transcript", json=payload)
    t_id = create_resp.json()["extracted_tickets"][0]["id"]

    assign_payload = {
        "assigned_staff": "Nurse Sarah Jenkins",
        "assigned_team": "Inpatient Floor Nursing",
        "assigned_to": "Floor Charge Nurse",
        "assigner": "Charge Nurse Supervisor"
    }
    assign_resp = client.post(f"/api/tickets/{t_id}/assign", json=assign_payload)
    assert assign_resp.status_code == 200
    assign_data = assign_resp.json()

    assert assign_data["assigned_staff"] == "Nurse Sarah Jenkins"
    assert assign_data["assigned_team"] == "Inpatient Floor Nursing"
    assert assign_data["assigned_to"] == "Floor Charge Nurse"

    logs = assign_data["audit_logs"]
    assert any("ASSIGNED" in l["action"] for l in logs)

def test_manual_escalation_tracking():
    """Escalating a ticket increases escalation level and records audit note."""
    payload = {
        "caller_name": "Staff",
        "patient_name": "Sam Taylor",
        "room_number": "Room 105",
        "raw_transcript": "Patient in Room 105 has high fever and needs urgent nursing evaluation.",
        "language": "en"
    }
    create_resp = client.post("/api/calls/process-transcript", json=payload)
    t_id = create_resp.json()["extracted_tickets"][0]["id"]

    esc_resp1 = client.post(f"/api/tickets/{t_id}/escalate", json={
        "escalation_reason": "No response after 15 minutes, temperature rising.",
        "escalated_by": "Floor Assistant"
    })
    assert esc_resp1.status_code == 200
    esc1_data = esc_resp1.json()
    assert esc1_data["escalation_level"] == 1
    assert "No response after 15 minutes" in esc1_data["escalation_reason"]

    # Escalate again to Level 2
    esc_resp2 = client.post(f"/api/tickets/{t_id}/escalate", json={
        "escalation_reason": "Physician intervention required immediately.",
        "escalated_by": "Head Nurse"
    })
    assert esc_resp2.status_code == 200
    esc2_data = esc_resp2.json()
    assert esc2_data["escalation_level"] == 2

def test_resolution_tracking_with_notes():
    """Resolving a ticket records resolution notes, resolved_by, and timestamp."""
    payload = {
        "caller_name": "Staff",
        "patient_name": "Walter White",
        "room_number": "Room 303",
        "raw_transcript": "Walter in Room 303 requires ice pack and repositioning.",
        "language": "en"
    }
    create_resp = client.post("/api/calls/process-transcript", json=payload)
    t_id = create_resp.json()["extracted_tickets"][0]["id"]

    resolve_resp = client.post(f"/api/tickets/{t_id}/resolve", json={
        "resolution_notes": "Ice pack applied and patient repositioned comfortably. Vitals normal.",
        "resolved_by": "Nurse Betty"
    })
    assert resolve_resp.status_code == 200
    res_data = resolve_resp.json()

    assert res_data["status"] == "RESOLVED"
    assert res_data["resolved_by"] == "Test Administrator"
    assert "Ice pack applied" in res_data["resolution_notes"]
    assert res_data["resolved_at"] is not None

def test_overdue_detection_and_query_filter():
    """Tickets past deadline are detected as overdue and filterable via query params."""
    with TestingSessionLocal() as db:
        overdue_ticket = Ticket(
            department="Rapid Response & Critical Nursing",
            category="Emergency and urgent clinical concerns",
            title="Overdue Emergency Task",
            description="Patient needs emergency evaluation",
            urgency="STAT_EMERGENCY",
            status="PENDING",
            sla_minutes=5,
            deadline_at=datetime.now(timezone.utc) - timedelta(minutes=15), # 15 minutes in the past
            room_number="Room 101",
            patient_name="John Doe",
            assigned_team="Rapid Response Team"
        )
        db.add(overdue_ticket)
        db.commit()
        db.refresh(overdue_ticket)
        t_id = overdue_ticket.id

    # Verify get_ticket marks is_overdue as True
    t_resp = client.get(f"/api/tickets/{t_id}")
    assert t_resp.status_code == 200
    assert t_resp.json()["is_overdue"] is True

    # Verify query by is_overdue=true
    overdue_list = client.get("/api/tickets?is_overdue=true").json()
    assert any(t["id"] == t_id for t in overdue_list)

    # Verify query by is_overdue=false excludes it
    not_overdue_list = client.get("/api/tickets?is_overdue=false").json()
    assert not any(t["id"] == t_id for t in not_overdue_list)

def test_auto_escalation_endpoint():
    """Calling /api/tickets/check-escalations automatically escalates breached overdue emergency tickets."""
    with TestingSessionLocal() as db:
        overdue_stat = Ticket(
            department="Rapid Response & Critical Nursing",
            category="Emergency and urgent clinical concerns",
            title="Unattended STAT Alert",
            description="Severe cardiac distress unattended",
            urgency="STAT_EMERGENCY",
            status="PENDING",
            sla_minutes=5,
            deadline_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            escalation_level=0,
            room_number="Room 102",
            patient_name="Jane Doe"
        )
        db.add(overdue_stat)
        db.commit()
        db.refresh(overdue_stat)
        t_id = overdue_stat.id

    check_resp = client.post("/api/tickets/check-escalations")
    assert check_resp.status_code == 200
    assert check_resp.json()["escalated_count"] >= 1

    updated_t = client.get(f"/api/tickets/{t_id}").json()
    assert updated_t["escalation_level"] == 2
    assert "Critical STAT emergency SLA breached" in updated_t["escalation_reason"]

def test_analytics_observability_includes_phase5_metrics():
    """Analytics endpoint exposes overdue, escalated, and unacknowledged ticket counts."""
    # Seed 1 unacknowledged overdue ticket
    with TestingSessionLocal() as db:
        t = Ticket(
            department="Rapid Response & Critical Nursing",
            category="Emergency and urgent clinical concerns",
            title="Metrics Test Task",
            description="Testing analytics",
            urgency="STAT_EMERGENCY",
            status="PENDING",
            is_acknowledged=False,
            escalation_level=1,
            sla_minutes=5,
            deadline_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            room_number="Room 999",
            patient_name="Test Patient"
        )
        db.add(t)
        db.commit()

    resp = client.get("/api/analytics")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_tickets"] >= 1
    assert data["overdue_tickets"] >= 1
    assert data["escalated_tickets"] >= 1
    assert data["unacknowledged_tickets"] >= 1
