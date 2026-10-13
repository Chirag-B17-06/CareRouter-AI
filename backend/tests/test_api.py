import os
import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import Base, get_db
from main import app

# In-memory SQLite for test isolation
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

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["stt_engine"] == "faster-whisper"
    assert "kn" in data["supported_languages"]
    assert "hi" in data["supported_languages"]
    assert "en" in data["supported_languages"]

def test_empty_state_initial():
    """Verify that dashboard starts completely empty with 0 fake calls and 0 fake tickets."""
    calls_resp = client.get("/api/calls")
    assert calls_resp.status_code == 200
    assert len(calls_resp.json()) == 0

    tickets_resp = client.get("/api/tickets")
    assert tickets_resp.status_code == 200
    assert len(tickets_resp.json()) == 0

    analytics_resp = client.get("/api/analytics")
    assert analytics_resp.status_code == 200
    analytics = analytics_resp.json()
    assert analytics["total_calls"] == 0
    assert analytics["total_tickets"] == 0
    assert analytics["emergency_count"] == 0

def test_audio_validation_empty_file():
    """Uploading an empty 0-byte audio file must be rejected with 400 Bad Request."""
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/audio/transcribe",
        files={"audio_file": ("test.webm", empty_file, "audio/webm")},
        data={"language": "auto"}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_audio_validation_invalid_format():
    """Uploading non-audio files must be rejected with 400 Bad Request."""
    fake_txt = io.BytesIO(b"Hello world text file")
    response = client.post(
        "/api/audio/transcribe",
        files={"audio_file": ("document.txt", fake_txt, "text/plain")},
        data={"language": "en"}
    )
    assert response.status_code == 400
    assert "unsupported audio format" in response.json()["detail"].lower()

def test_audio_validation_oversized():
    """Audio files larger than 25MB must be rejected."""
    # We test the validator directly
    from audio_transcriber import validate_audio_file
    with pytest.raises(ValueError, match="exceeds the maximum limit"):
        validate_audio_file("huge.wav", 30 * 1024 * 1024)

def test_process_english_multi_intent_and_stat():
    """Test real multi-intent extraction with STAT emergency in English."""
    payload = {
        "caller_name": "Sarah",
        "patient_name": "Arthur Pendelton",
        "room_number": "Room 314",
        "raw_transcript": (
            "Hi, this is Sarah calling about Arthur in Room 314. "
            "His IV machine has been beeping incessantly and his left arm looks swollen and red! "
            "Also, he has not received his diabetic lunch tray yet and his blood sugar might drop. "
            "And one more thing, we need to speak with Dr. Chen regarding his discharge paperwork before 3 PM."
        ),
        "language": "en"
    }
    response = client.post("/api/calls/process-transcript", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["emergency_detected"] is True
    assert len(data["extracted_tickets"]) == 3

    departments = [t["department"] for t in data["extracted_tickets"]]
    urgencies = [t["urgency"] for t in data["extracted_tickets"]]

    assert "Rapid Response & Critical Nursing" in departments
    assert "STAT_EMERGENCY" in urgencies
    assert any("Dietary" in d for d in departments)
    assert any("Administration" in d for d in departments)

def test_process_hindi_multi_intent_and_devanagari_script():
    """Test real multi-intent extraction with Hindi Devanagari script preservation and STAT emergency."""
    payload = {
        "caller_name": "Rajesh Kumar",
        "patient_name": "Suresh Kumar",
        "room_number": "कमरा 108",
        "raw_transcript": (
            "नमस्ते, मैं कमरा 108 से बोल रहा हूँ। "
            "मरीज के सीने में बहुत तेज दर्द हो रहा है और सांस लेने में तकलीफ है! "
            "इसके अलावा उन्हें दोपहर का खाना अभी तक नहीं मिला है और भूख लगी है। "
            "साथ ही डिस्चार्ज के कागजात के बारे में डॉक्टर से बात करनी है।"
        ),
        "language": "hi"
    }
    response = client.post("/api/calls/process-transcript", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["emergency_detected"] is True
    assert data["call"]["language"] == "hi"
    assert len(data["extracted_tickets"]) == 3

    # Check Devanagari script is preserved in raw_quote
    quotes = [t["raw_quote"] for t in data["extracted_tickets"]]
    assert any("सीने में बहुत तेज दर्द" in q for q in quotes)
    assert any("दोपहर का खाना" in q for q in quotes)
    assert any("डिस्चार्ज" in q for q in quotes)

    departments = [t["department"] for t in data["extracted_tickets"]]
    assert "Rapid Response & Critical Nursing" in departments
    assert any("Dietary" in d for d in departments)
    assert any("Administration" in d for d in departments)

def test_process_kannada_multi_intent_and_kannada_script():
    """Test real multi-intent extraction with Kannada script preservation and STAT emergency."""
    payload = {
        "caller_name": "Manjunath",
        "patient_name": "Ramesh",
        "room_number": "ಕೋಣೆ 422",
        "raw_transcript": (
            "ನಮಸ್ಕಾರ, ಇದು ಕೋಣೆ 422 ರಿಂದ ಕರೆ ಮಾಡುತ್ತಿದ್ದೇನೆ. "
            "ರೋಗಿಗೆ ಎದೆ ನೋವು ತುಂಬಾ ಜಾಸ್ತಿ ಇದೆ ಮತ್ತು ಉಸಿರಾಟದ ತೊಂದರೆ ಇದೆ! "
            "ಹಾಗೆಯೇ ಅವರ ಬಿಪಿ ಮಾತ್ರೆಗಳ ಬಗ್ಗೆ ಫಾರ್ಮಸಿ ಜೊತೆ ಮಾತನಾಡಬೇಕು. "
            "ಜೊತೆಗೆ ಕೊಠಡಿಯಲ್ಲಿ ನೆಲದ ಮೇಲೆ ನೀರು ಬಿದ್ದಿದೆ ಸ್ವಚ್ಛತೆ ಮಾಡಬೇಕು."
        ),
        "language": "kn"
    }
    response = client.post("/api/calls/process-transcript", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["emergency_detected"] is True
    assert data["call"]["language"] == "kn"
    assert len(data["extracted_tickets"]) == 3

    # Check Kannada script is preserved in raw_quote
    quotes = [t["raw_quote"] for t in data["extracted_tickets"]]
    assert any("ಎದೆ ನೋವು" in q for q in quotes)
    assert any("ಮಾತ್ರೆಗಳ" in q for q in quotes)
    assert any("ನೆಲದ ಮೇಲೆ ನೀರು" in q for q in quotes)

    departments = [t["department"] for t in data["extracted_tickets"]]
    assert "Rapid Response & Critical Nursing" in departments
    assert any("Pharmacy" in d for d in departments)
    assert any("Facilities" in d for d in departments)

def test_emergency_negation_handling_english():
    """Symptom keywords that are explicitly negated must NOT trigger a STAT Emergency."""
    payload = {
        "caller_name": "David",
        "patient_name": "Mary",
        "room_number": "Room 205",
        "raw_transcript": (
            "Patient has a mild tension headache, but denies chest pain and has no shortness of breath. "
            "Also can we get an extra pillow and water pitcher?"
        ),
        "language": "en"
    }
    response = client.post("/api/calls/process-transcript", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Emergency should be FALSE because chest pain and shortness of breath are negated
    assert data["emergency_detected"] is False
    for t in data["extracted_tickets"]:
        assert t["urgency"] != "STAT_EMERGENCY"

def test_emergency_negation_handling_hindi():
    """Hindi negation ('सीने में दर्द नहीं है') must NOT trigger STAT emergency."""
    payload = {
        "caller_name": "Pooja",
        "patient_name": "Sunita",
        "room_number": "कमरा 302",
        "raw_transcript": (
            "मरीज को थोड़ा चक्कर आ रहा है, लेकिन सीने में दर्द नहीं है। "
            "कृपया नर्स को बीपी चेक करने के लिए भेजें।"
        ),
        "language": "hi"
    }
    response = client.post("/api/calls/process-transcript", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["emergency_detected"] is False

def test_emergency_negation_handling_kannada():
    """Kannada negation ('ಎದೆ ನೋವು ಇಲ್ಲ') must NOT trigger STAT emergency."""
    payload = {
        "caller_name": "Sunil",
        "patient_name": "Anand",
        "room_number": "ಕೋಣೆ 105",
        "raw_transcript": (
            "ರೋಗಿಗೆ ಎದೆ ನೋವು ಇಲ್ಲ, ಆದರೆ ಸ್ವಲ್ಪ ಸುಸ್ತು ಅನಿಸುತ್ತಿದೆ. "
            "ದಯವಿಟ್ಟು ನರ್ಸ್ ಬಂದು ನೋಡಿ."
        ),
        "language": "kn"
    }
    response = client.post("/api/calls/process-transcript", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["emergency_detected"] is False

def test_duplicate_submission_guard():
    """Submitting the exact same transcript twice immediately should return existing call without duplicating."""
    payload = {
        "caller_name": "Caller A",
        "patient_name": "Patient A",
        "room_number": "Room 501",
        "raw_transcript": "Patient requests pain medication refill and lunch tray.",
        "language": "en"
    }
    res1 = client.post("/api/calls/process-transcript", json=payload)
    assert res1.status_code == 200
    id1 = res1.json()["call"]["id"]

    res2 = client.post("/api/calls/process-transcript", json=payload)
    assert res2.status_code == 200
    id2 = res2.json()["call"]["id"]

    assert id1 == id2
    # Check total calls count remains 1
    calls = client.get("/api/calls").json()
    assert len(calls) == 1

def test_ticket_status_update_and_notes():
    """Test advancing status from PENDING to IN_PROGRESS to RESOLVED and adding triage notes."""
    payload = {
        "raw_transcript": "Patient in Room 102 needs antibiotic allergy verification before evening dose."
    }
    res = client.post("/api/calls/process-transcript", json=payload)
    ticket_id = res.json()["extracted_tickets"][0]["id"]

    # Update status
    patch_res = client.patch(f"/api/tickets/{ticket_id}", json={
        "status": "IN_PROGRESS",
        "assigned_to": "Pharmacist Dr. Rao"
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "IN_PROGRESS"
    assert patch_res.json()["assigned_to"] == "Pharmacist Dr. Rao"

    # Add clinical note
    note_res = client.post(f"/api/tickets/{ticket_id}/notes", json={
        "note": "Cross-checked with EHR: No active penicillin allergy found.",
        "author": "Dr. Rao"
    })
    assert note_res.status_code == 200
    # Actor identity now comes from the authenticated session, not from client-supplied names.
    assert "Test Administrator" in note_res.json()["triage_notes"]

def test_delete_call_and_tickets():
    """Test deleting a call record and verifying its tickets are removed."""
    payload = {
        "raw_transcript": "Test call to be deleted soon. Patient needs water pitcher."
    }
    res = client.post("/api/calls/process-transcript", json=payload)
    call_id = res.json()["call"]["id"]

    # Delete call
    del_res = client.delete(f"/api/calls/{call_id}")
    assert del_res.status_code == 200

    # Verify call and tickets are gone
    assert len(client.get("/api/calls").json()) == 0
    assert len(client.get("/api/tickets").json()) == 0

def test_delete_resolved_ticket_success():
    """Deleting a ticket with status RESOLVED must succeed without deleting parent call or sibling tickets."""
    payload = {
        "raw_transcript": "Patient in Room 303 needs pillow and also needs water pitcher."
    }
    res = client.post("/api/calls/process-transcript", json=payload)
    assert res.status_code == 200
    tickets = res.json()["extracted_tickets"]
    assert len(tickets) >= 2
    t1_id = tickets[0]["id"]
    t2_id = tickets[1]["id"]
    call_id = res.json()["call"]["id"]

    # Mark ticket 1 as RESOLVED
    patch_res = client.patch(f"/api/tickets/{t1_id}", json={"status": "RESOLVED"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "RESOLVED"

    # Delete resolved ticket 1
    del_res = client.delete(f"/api/tickets/{t1_id}")
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json()["message"].lower()

    # Verify ticket 1 is gone
    get_res = client.get(f"/api/tickets/{t1_id}")
    assert get_res.status_code == 404

    # Verify ticket 2 and Call STILL EXIST (no accidental cascading deletion)
    get_t2 = client.get(f"/api/tickets/{t2_id}")
    assert get_t2.status_code == 200

    get_call = client.get(f"/api/calls/{call_id}")
    assert get_call.status_code == 200

def test_delete_unresolved_ticket_rejected():
    """Attempting to delete a ticket that is PENDING or IN_PROGRESS must be rejected with 400."""
    payload = {
        "raw_transcript": "Patient has acute chest pain and shortness of breath in Room 101."
    }
    res = client.post("/api/calls/process-transcript", json=payload)
    assert res.status_code == 200
    ticket_id = res.json()["extracted_tickets"][0]["id"]

    # Attempt to delete PENDING ticket -> Must fail
    del_res = client.delete(f"/api/tickets/{ticket_id}")
    assert del_res.status_code == 400
    assert "only tickets with status 'resolved' can be deleted" in del_res.json()["detail"].lower()

    # Advance to IN_PROGRESS and attempt to delete -> Must fail
    client.patch(f"/api/tickets/{ticket_id}", json={"status": "IN_PROGRESS"})
    del_res2 = client.delete(f"/api/tickets/{ticket_id}")
    assert del_res2.status_code == 400
    assert "only tickets with status 'resolved' can be deleted" in del_res2.json()["detail"].lower()

def test_empty_transcript_submission_rejected():
    """Submitting empty or whitespace-only transcript must be rejected with 400."""
    res1 = client.post("/api/calls/process-transcript", json={"raw_transcript": ""})
    assert res1.status_code in (400, 422)

    res2 = client.post("/api/calls/process-transcript", json={"raw_transcript": "    "})
    assert res2.status_code == 400
    assert "empty or blank transcript" in res2.json()["detail"].lower()

def test_stream_audio_file_endpoint():
    """Streaming nonexistent audio should 404; existing audio file should serve 200."""
    res404 = client.get("/api/audio/nonexistent_audio_file.wav")
    assert res404.status_code == 404

    # Create a small dummy file in UPLOAD_DIR
    from audio_transcriber import UPLOAD_DIR
    test_file = UPLOAD_DIR / "test_sample.wav"
    test_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00data\x00\x00\x00\x00")
    try:
        res200 = client.get("/api/audio/test_sample.wav")
        assert res200.status_code == 200
        assert "audio" in res200.headers.get("content-type", "")
    finally:
        if test_file.exists():
            test_file.unlink(missing_ok=True)
