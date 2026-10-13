import os
import sys
import json
import sqlite3
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import Base, Call, Ticket, AuditLog, get_db, engine as prod_engine
from main import app

# Test engine for isolated in-memory testing with foreign keys enabled
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

@event.listens_for(test_engine, "connect")
def set_test_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
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

def test_sqlite_pragmas_wal_and_foreign_keys(tmp_path):
    """Verify that SQLite connection listener enables foreign keys and WAL mode on file databases."""
    db_file = tmp_path / "pragma_test.db"
    file_engine = create_engine(
        f"sqlite:///{str(db_file)}",
        connect_args={"check_same_thread": False}
    )

    @event.listens_for(file_engine, "connect")
    def apply_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    with file_engine.connect() as conn:
        fk_result = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert fk_result == 1, "Foreign keys must be enabled (PRAGMA foreign_keys = 1)"

        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert journal_mode.lower() == "wal", f"Journal mode should be WAL, got {journal_mode}"

def test_foreign_key_cascade_deletion():
    """Verify that deleting a Call automatically cascades and deletes child Tickets and AuditLogs."""
    # 1. Create a call with ticket and audit log
    payload = {
        "caller_name": "Priya",
        "patient_name": "Ramesh",
        "room_number": "Room 402",
        "raw_transcript": "Patient in Room 402 is complaining of severe dizziness and needs blood pressure checked.",
        "language": "en"
    }
    response = client.post("/api/calls/process-transcript", json=payload)
    assert response.status_code == 200
    data = response.json()
    call_id = data["call"]["id"]
    ticket_ids = [t["id"] for t in data["extracted_tickets"]]
    assert len(ticket_ids) > 0

    # Verify tickets exist
    for tid in ticket_ids:
        t_res = client.get(f"/api/tickets/{tid}")
        assert t_res.status_code == 200

    # 2. Delete the parent call
    del_res = client.delete(f"/api/calls/{call_id}")
    assert del_res.status_code == 200

    # 3. Verify parent call is gone
    call_get = client.get(f"/api/calls/{call_id}")
    assert call_get.status_code == 404

    # 4. Verify cascade: child tickets and audit logs are deleted
    for tid in ticket_ids:
        t_get = client.get(f"/api/tickets/{tid}")
        assert t_get.status_code == 404

def test_idempotency_key_deduplication():
    """Verify that repeated requests with the same idempotency_key return the cached call without duplicates."""
    idempotency_key = "req_care_router_unique_key_999"
    payload = {
        "idempotency_key": idempotency_key,
        "caller_name": "Kavitha",
        "patient_name": "Suresh",
        "room_number": "Room 205",
        "raw_transcript": "Doctor requested an ECG and potassium level recheck for patient in 205.",
        "language": "en"
    }

    # First request
    res1 = client.post("/api/calls/process-transcript", json=payload)
    assert res1.status_code == 200
    data1 = res1.json()
    call1_id = data1["call"]["id"]
    tickets1 = data1["extracted_tickets"]

    # Second request with same idempotency_key
    res2 = client.post("/api/calls/process-transcript", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    call2_id = data2["call"]["id"]
    assert data2["engine_used"] == "CareRouter Idempotent Cache"

    # Must be exact same call ID and same ticket IDs
    assert call1_id == call2_id
    assert [t["id"] for t in tickets1] == [t["id"] for t in data2["extracted_tickets"]]

    # Total calls in database should still be exactly 1
    calls = client.get("/api/calls").json()
    assert len(calls) == 1

def test_time_window_duplicate_guard():
    """Verify that repeated requests within the 60-second window are deduplicated without idempotency_key."""
    payload = {
        "caller_name": "Nurse Anitha",
        "patient_name": "Meera",
        "room_number": "Room 108",
        "raw_transcript": "Patient in 108 is asking for morning dose of metformin and insulin chart.",
        "language": "en"
    }

    res1 = client.post("/api/calls/process-transcript", json=payload)
    assert res1.status_code == 200
    id1 = res1.json()["call"]["id"]

    res2 = client.post("/api/calls/process-transcript", json=payload)
    assert res2.status_code == 200
    assert res2.json()["engine_used"] == "CareRouter Duplicate Guard"
    id2 = res2.json()["call"]["id"]

    assert id1 == id2
    calls = client.get("/api/calls").json()
    assert len(calls) == 1

def test_backward_compatible_column_migrations(tmp_path):
    """Verify that SQLite database missing newer columns is safely migrated without losing existing records."""
    db_file = tmp_path / "legacy_test.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    # Create older legacy tables
    cur.execute("""
        CREATE TABLE calls (
            id INTEGER PRIMARY KEY,
            caller_name VARCHAR(100),
            patient_name VARCHAR(100),
            room_number VARCHAR(50),
            raw_transcript TEXT NOT NULL,
            language VARCHAR(20),
            created_at DATETIME
        )
    """)
    cur.execute("""
        CREATE TABLE tickets (
            id INTEGER PRIMARY KEY,
            call_id INTEGER,
            department VARCHAR(100) NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            raw_quote TEXT,
            translated_quote TEXT,
            language VARCHAR(20),
            urgency VARCHAR(50) NOT NULL,
            status VARCHAR(50),
            clinical_flags TEXT,
            assigned_to VARCHAR(100),
            room_number VARCHAR(50),
            patient_name VARCHAR(100),
            triage_notes TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )
    """)
    cur.execute("""
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER NOT NULL,
            action VARCHAR(100) NOT NULL,
            created_at DATETIME
        )
    """)

    # Insert a legacy row into calls and tickets
    now_str = datetime.now(timezone.utc).isoformat()
    cur.execute("""
        INSERT INTO calls (caller_name, patient_name, room_number, raw_transcript, language, created_at)
        VALUES ('Legacy Caller', 'Legacy Patient', '101', 'Legacy patient transcript text', 'en', ?)
    """, (now_str,))
    cur.execute("""
        INSERT INTO tickets (call_id, department, title, description, urgency, status, room_number, patient_name, created_at, updated_at)
        VALUES (1, 'Nursing', 'Legacy Task', 'Legacy task description', 'ROUTINE', 'PENDING', '101', 'Legacy Patient', ?, ?)
    """, (now_str, now_str))
    conn.commit()
    conn.close()

    # Now run migration logic against this legacy DB file
    import database
    orig_url = database.DATABASE_URL
    try:
        database.DATABASE_URL = f"sqlite:///{str(db_file)}"
        database.init_db()

        # Verify that new columns were added and legacy record still exists
        migrated_conn = sqlite3.connect(str(db_file))
        m_cur = migrated_conn.cursor()

        # Check calls columns
        m_cur.execute("PRAGMA table_info(calls)")
        call_cols = {row[1] for row in m_cur.fetchall()}
        assert "idempotency_key" in call_cols
        assert "caller_phone" in call_cols
        assert "translated_transcript" in call_cols
        assert "summary" in call_cols

        # Check tickets columns
        m_cur.execute("PRAGMA table_info(tickets)")
        ticket_cols = {row[1] for row in m_cur.fetchall()}
        assert "category" in ticket_cols
        assert "urgency_evidence" in ticket_cols
        assert "requires_human_review" in ticket_cols
        assert "sla_minutes" in ticket_cols
        assert "is_reviewed" in ticket_cols

        # Check audit_logs columns
        m_cur.execute("PRAGMA table_info(audit_logs)")
        audit_cols = {row[1] for row in m_cur.fetchall()}
        assert "actor" in audit_cols
        assert "note" in audit_cols

        # Verify legacy data preserved
        m_cur.execute("SELECT caller_name, patient_name, raw_transcript FROM calls WHERE id = 1")
        row = m_cur.fetchone()
        assert row == ("Legacy Caller", "Legacy Patient", "Legacy patient transcript text")

        m_cur.execute("SELECT title, urgency, department FROM tickets WHERE id = 1")
        t_row = m_cur.fetchone()
        assert t_row == ("Legacy Task", "ROUTINE", "Nursing")

        migrated_conn.close()

    finally:
        database.DATABASE_URL = orig_url

def test_safe_fallback_on_nlp_parser_degradation(monkeypatch):
    """Verify that if the NLP engine throws an exception, CareRouter never drops the clinical call."""
    import main

    def mock_broken_nlp(*args, **kwargs):
        raise RuntimeError("Simulated transient NLP parser failure")

    monkeypatch.setattr(main, "process_real_transcript", mock_broken_nlp)

    payload = {
        "caller_name": "Attendant",
        "patient_name": "Devi",
        "room_number": "Room 303",
        "raw_transcript": "Patient feeling uncomfortable, please send someone.",
        "language": "en"
    }

    res = client.post("/api/calls/process-transcript", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Safe fallback ticket created
    assert "Safe Fallback" in data["engine_used"]
    assert len(data["extracted_tickets"]) == 1
    ticket = data["extracted_tickets"][0]
    assert ticket["requires_human_review"] is True
    assert ticket["urgency"] == "URGENT"
    assert "NLP engine error" in ticket["human_review_reason"]
    assert ticket["department"] == "Rapid Response & Critical Nursing"

    # Verify audit log reflects creation
    t_get = client.get(f"/api/tickets/{ticket['id']}")
    assert t_get.status_code == 200
    assert any(a["action"] == "FLAGGED_FOR_REVIEW" for a in t_get.json()["audit_logs"])

def test_transaction_rollback_guarantee(monkeypatch):
    """Verify that a database transaction failure rolls back cleanly without leaving partial records."""
    from sqlalchemy.orm import Session as SASession

    original_commit = SASession.commit
    fail_state = {"triggered": False}

    def failing_commit(self):
        fail_state["triggered"] = True
        raise RuntimeError("Simulated mid-commit database I/O fault")

    payload = {
        "caller_name": "Test",
        "patient_name": "Rollback Test",
        "room_number": "999",
        "raw_transcript": "Testing rollback safety during database crash.",
        "language": "en"
    }

    monkeypatch.setattr(SASession, "commit", failing_commit)

    # Post should fail with 500
    res = client.post("/api/calls/process-transcript", json=payload)
    assert res.status_code == 500
    assert fail_state["triggered"] is True

    # Restore commit
    monkeypatch.setattr(SASession, "commit", original_commit)

    # Verify no partial calls or tickets exist in the database
    calls = client.get("/api/calls").json()
    assert len(calls) == 0

    tickets = client.get("/api/tickets").json()
    assert len(tickets) == 0

def test_input_validation_empty_and_blank_transcripts():
    """Verify that whitespace-only and blank transcripts are rejected with 400 or 422."""
    res1 = client.post("/api/calls/process-transcript", json={
        "raw_transcript": "   "
    })
    assert res1.status_code in (400, 422)

    res2 = client.post("/api/calls/process-transcript", json={
        "raw_transcript": ""
    })
    assert res2.status_code in (400, 422)

def test_input_validation_invalid_review_action():
    """Verify that invalid human review action strings are rejected."""
    # First create a valid ticket
    payload = {
        "raw_transcript": "Patient in Room 204 needs catheter checked.",
        "language": "en"
    }
    c_res = client.post("/api/calls/process-transcript", json=payload)
    ticket_id = c_res.json()["extracted_tickets"][0]["id"]

    # Send invalid review action
    rev_res = client.post(f"/api/tickets/{ticket_id}/review", json={
        "action": "INVALID_ACTION",
        "reviewer_name": "Dr. Kumar"
    })
    assert rev_res.status_code == 422
