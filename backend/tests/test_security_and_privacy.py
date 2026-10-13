import os
import sys
import io
import csv
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import Base, Call, Ticket, AuditLog, get_db
from main import app
from security import (
    mask_phone_number, redact_pii_text, sanitize_csv_cell,
    validate_safe_audio_filename, ALLOWED_AUDIO_EXTENSIONS
)

# Test engine for isolated in-memory testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
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

def test_security_headers_present():
    """Verify that HTTP security headers (CSP, nosniff, frame-options, etc.) are attached to API responses."""
    response = client.get("/api/health")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "strict-origin" in headers.get("Referrer-Policy", "")
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")

def test_audio_path_traversal_prevention():
    """Verify that path traversal attempts on audio streaming endpoints are blocked."""
    from fastapi import HTTPException
    from pathlib import Path
    import tempfile

    # 1. Direct validation tests on null bytes and traversal sequences
    with pytest.raises(HTTPException) as exc1:
        validate_safe_audio_filename("null\x00byte.wav", Path(tempfile.gettempdir()))
    assert exc1.value.status_code == 400

    with pytest.raises(HTTPException) as exc2:
        validate_safe_audio_filename("../../secret.wav", Path(tempfile.gettempdir()))
    assert exc2.value.status_code == 400

    with pytest.raises(HTTPException) as exc3:
        validate_safe_audio_filename("..\\windows\\system.wav", Path(tempfile.gettempdir()))
    assert exc3.value.status_code == 400

    # 2. HTTP endpoint requests with traversal attempts
    traversal_http_payloads = [
        "..%2F..%2Fsecret.wav",
        "nested/sub/file.wav",
        "invalid_chars$.wav",
        "script<tag>.wav"
    ]
    for bad_name in traversal_http_payloads:
        res1 = client.get(f"/api/audio/{bad_name}")
        assert res1.status_code in (400, 404), f"Expected rejection for {bad_name}, got {res1.status_code}"

        res2 = client.get(f"/api/audio/play/{bad_name}")
        assert res2.status_code in (400, 404), f"Expected rejection for {bad_name}, got {res2.status_code}"

def test_prohibited_file_extensions_blocked():
    """Verify that non-audio file extensions are rejected even if filename has no traversal."""
    prohibited_files = [
        "care_router.db",
        "database.py",
        "settings.env",
        "config.json",
        "exploit.exe",
        "document.pdf"
    ]
    for bad_file in prohibited_files:
        res = client.get(f"/api/audio/{bad_file}")
        assert res.status_code == 400
        assert "Prohibited file format" in res.json().get("detail", "")

def test_csv_formula_injection_defense():
    """Verify that values starting with =, +, -, @, \\t are neutralized with a leading single quote."""
    # Test helper directly
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("-123") == "'-123"
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_csv_cell("\tDangerousTab") == "'\tDangerousTab"
    assert sanitize_csv_cell("Normal Clinical Text") == "Normal Clinical Text"

    # Test via CSV export endpoint
    # Create ticket with formula injection in title and description
    payload = {
        "caller_name": "Test Attendant",
        "patient_name": "=CMD('calc')",
        "room_number": "@204",
        "raw_transcript": "=HYPERLINK('http://malicious.com','Click Here') Patient in Room 204 needs catheter checked.",
        "language": "en"
    }
    c_res = client.post("/api/calls/process-transcript", json=payload)
    assert c_res.status_code == 200

    # Export CSV
    export_res = client.get("/api/export/tickets?format=csv")
    assert export_res.status_code == 200
    csv_text = export_res.text

    # Verify formulas are neutralized with single quote prefix
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) >= 2 # Header + at least 1 ticket

    # Patient name and room columns should be escaped
    escaped_patient = False
    escaped_room = False
    for row in rows[1:]:
        patient_cell = row[2]
        room_cell = row[3]
        if patient_cell.startswith("'="):
            escaped_patient = True
        if room_cell.startswith("'@"):
            escaped_room = True

    assert escaped_patient, "Patient name starting with '=' must be escaped with leading quote"
    assert escaped_room, "Room starting with '@' must be escaped with leading quote"

def test_deidentified_export_hipaa_compliance():
    """Verify that de_identify=true redacts patient names, rooms, and PII in exports."""
    payload = {
        "caller_name": "Rohan",
        "caller_phone": "+91 9876543210",
        "patient_name": "Vikram Malhotra",
        "room_number": "ICU Bed 4",
        "raw_transcript": "Patient Vikram Malhotra (Phone: 9876543210, Aadhaar: 1234 5678 9012) is breathless.",
        "language": "en"
    }
    c_res = client.post("/api/calls/process-transcript", json=payload)
    assert c_res.status_code == 200

    # 1. Test CSV de-identification
    csv_res = client.get("/api/export/tickets?format=csv&de_identify=true")
    assert csv_res.status_code == 200
    csv_content = csv_res.text

    # Patient name should NOT contain real name
    assert "Vikram Malhotra" not in csv_content
    assert "Patient-PT" in csv_content
    assert "[REDACTED]" in csv_content # Room number redacted
    assert "1234 5678 9012" not in csv_content # Aadhaar redacted

    # 2. Test JSON de-identification
    json_res = client.get("/api/export/tickets?format=json&de_identify=true")
    assert json_res.status_code == 200
    json_data = json_res.json()
    assert len(json_data) >= 1
    t = json_data[0]
    assert t["patient_name"].startswith("Patient-PT")
    assert t["room_number"] == "[REDACTED]"
    assert "1234 5678 9012" not in t["description"]

def test_phone_masking_utility():
    """Verify phone masking utility functions."""
    assert mask_phone_number("+91 9876543210") == "+91 98765 XXXXX"
    assert mask_phone_number("9876543210") == "+91 98765 XXXXX"
    assert mask_phone_number("") == ""
    assert mask_phone_number(None) == ""

def test_pii_redaction_utility():
    """Verify regex redaction of Aadhaar and 10-digit phone numbers in clinical notes."""
    text = "Call back Dr. Sharma at 9845123456 or patient family at +91 9123456789. Aadhaar 4321 8765 2109."
    redacted = redact_pii_text(text)
    assert "9845123456" not in redacted
    assert "9123456789" not in redacted
    assert "4321 8765 2109" not in redacted
    assert "[ID-REDACTED]" in redacted
    assert "+91" in redacted
