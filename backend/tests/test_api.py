import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import from backend
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import Base, get_db
from main import app, seed_initial_demo_data

# Use in-memory SQLite with StaticPool so all connections share the same memory instance
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

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    seed_initial_demo_data(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["demo_mode"] is True

def test_get_scenarios():
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) == 3
    assert scenarios[0]["id"] == "scenario-1"
    assert scenarios[1]["id"] == "scenario-2"
    assert scenarios[2]["id"] == "scenario-3"

def test_process_scenario_1_decomposition():
    payload = {
        "caller_name": "Sarah Pendelton",
        "caller_phone": "+1 555-0199",
        "patient_name": "Arthur Pendelton",
        "room_number": "Room 314",
        "raw_transcript": (
            "Hi, this is Sarah calling about my father Arthur Pendelton in Room 314. "
            "His IV machine has been beeping incessantly for twenty minutes and his left arm looks swollen and red! "
            "Also, he hasn't received his diabetic lunch tray yet and his blood sugar might crash. "
            "And one more thing, we need to speak with Dr. Chen regarding his discharge paperwork before 3 PM "
            "because our medical transport is already booked."
        )
    }
    response = client.post("/api/calls/process", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["emergency_detected"] is True
    assert len(data["extracted_tickets"]) == 3

    # Check departments extracted
    departments = [t["department"] for t in data["extracted_tickets"]]
    urgencies = [t["urgency"] for t in data["extracted_tickets"]]

    assert "Rapid Response & Critical Nursing" in departments
    assert "STAT_EMERGENCY" in urgencies
    assert any("Dietary" in d for d in departments)
    assert any("Administration" in d for d in departments)

def test_ticket_filtering_and_search():
    # Tickets are already seeded
    response = client.get("/api/tickets?urgency=STAT_EMERGENCY")
    assert response.status_code == 200
    tickets = response.json()
    assert len(tickets) > 0
    for t in tickets:
        assert t["urgency"] == "STAT_EMERGENCY"

    # Search by room number
    resp_search = client.get("/api/tickets?search=314")
    assert resp_search.status_code == 200
    search_tickets = resp_search.json()
    assert len(search_tickets) > 0
    for t in search_tickets:
        assert "314" in t["room_number"] or "314" in t["title"] or "314" in t["description"]

def test_ticket_status_update_and_audit_trail():
    # Get a ticket
    resp = client.get("/api/tickets")
    tickets = resp.json()
    ticket_id = tickets[0]["id"]

    # Update status to RESOLVED
    update_resp = client.patch(f"/api/tickets/{ticket_id}", json={
        "status": "RESOLVED",
        "assigned_to": "Nurse Specialist Jackson"
    })
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["status"] == "RESOLVED"
    assert updated["assigned_to"] == "Nurse Specialist Jackson"

    # Check audit log recorded
    assert len(updated["audit_logs"]) >= 1
    assert any("RESOLVED" in a["note"] for a in updated["audit_logs"])

def test_add_ticket_note():
    resp = client.get("/api/tickets")
    ticket_id = resp.json()[0]["id"]

    note_resp = client.post(f"/api/tickets/{ticket_id}/notes", json={
        "note": "IV line inspected. Catheter replaced. Swelling subsided.",
        "author": "Dr. Miller"
    })
    assert note_resp.status_code == 200
    ticket = note_resp.json()
    assert "Dr. Miller" in ticket["triage_notes"]
    assert "Swelling subsided" in ticket["triage_notes"]

def test_analytics_metrics():
    response = client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_calls"] >= 3
    assert data["total_tickets"] >= 9
    assert data["emergency_count"] >= 1
    assert "Rapid Response & Critical Nursing" in data["department_distribution"]

def test_scenario_2_decomposition():
    sc2 = client.get("/api/scenarios").json()[1]
    response = client.post("/api/calls/process", json={
        "caller_name": sc2["caller_name"],
        "patient_name": sc2["patient_name"],
        "room_number": sc2["room_number"],
        "raw_transcript": sc2["transcript"]
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["extracted_tickets"]) == 3
    departments = [t["department"] for t in data["extracted_tickets"]]
    assert any("Pharmacy" in d for d in departments)
    assert any("Nursing" in d for d in departments)

def test_scenario_3_decomposition_and_fall_stat():
    sc3 = client.get("/api/scenarios").json()[2]
    response = client.post("/api/calls/process", json={
        "caller_name": sc3["caller_name"],
        "patient_name": sc3["patient_name"],
        "room_number": sc3["room_number"],
        "raw_transcript": sc3["transcript"]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["emergency_detected"] is True
    assert any("ACTIVE_FALL_RISK" in t["clinical_flags"] for t in data["extracted_tickets"])
    assert any("ENVIRONMENTAL_SLIP_HAZARD" in t["clinical_flags"] for t in data["extracted_tickets"])

def test_custom_call_extraction():
    custom_transcript = (
        "Good morning triage desk, this is nurse Kelly calling regarding patient Marcus Bell in Room 502. "
        "The patient is experiencing intense nausea and vomiting after his chemotherapy infusion. "
        "Also, the bathroom faucet in 502 is leaking heavily all over the floor."
    )
    response = client.post("/api/calls/process", json={
        "raw_transcript": custom_transcript
    })
    assert response.status_code == 200
    data = response.json()
    assert data["call"]["patient_name"] == "Marcus Bell"
    assert data["call"]["room_number"] == "Room 502"
    assert len(data["extracted_tickets"]) >= 2
