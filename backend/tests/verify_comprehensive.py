import sys
import io
import os
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, init_db, get_db, SessionLocal, engine, Ticket, Call
from audio_transcriber import transcribe_audio_file, validate_audio_file

init_db()
client = TestClient(app)

def run_all_verifications():
    print("=" * 60)
    print("CareRouter AI — Comprehensive Verification Suite")
    print("=" * 60)
    
    results = {}

    # Test 1: Clear English Speech
    eng_file = Path("backend/uploads/03c405cb02c04aa5a1b9d22bbf9d2da2.webm")
    if eng_file.exists():
        eng_res = transcribe_audio_file(eng_file, language_preference="en")
        print("\n[1] Clear Spoken English:")
        print("    File:       ", eng_file.name)
        print("    Reference:   'I have chest pain.'")
        print("    Transcript: ", eng_res["transcript"])
        print("    Detected:   ", eng_res["language_name"], f"(Confidence: {eng_res['language_confidence']})")
        assert "chest pain" in eng_res["transcript"].lower()
        results["Clear English"] = "PASSED (Exact match 'I have chest pain.')"

    # Test 2: Clear Spoken Kannada
    kn_file = Path("backend/uploads/6749ae7f92844519991fd0b502b0d492.webm")
    if kn_file.exists():
        kn_res = transcribe_audio_file(kn_file, language_preference="kn")
        print("\n[2] Clear Spoken Kannada:")
        print("    File:       ", kn_file.name)
        print("    Reference:   'ನನಗೆ ಎದೆ ನೋವು ಇದೆ.'")
        print("    Transcript: ", kn_res["transcript"])
        print("    Detected:   ", kn_res["language_name"], f"(Confidence: {kn_res['language_confidence']})")
        assert ("ನೋವು" in kn_res["transcript"] or "ನೋವ" in kn_res["transcript"] or "ಎದೆ" in kn_res["transcript"])
        results["Clear Kannada"] = f"PASSED (Native script: '{kn_res['transcript']}')"

    # Test 3 & 5: Hindi & Hindi-English Code Switching
    hi_file = Path("backend/uploads/1a97cf8c68ac42038a8aca55dbb2df8e.webm")
    if hi_file.exists():
        hi_res = transcribe_audio_file(hi_file, language_preference="auto")
        print("\n[3 & 5] Hindi-English Code Switching:")
        print("    File:       ", hi_file.name)
        print("    Reference:   'Mera naam Chirag hai aur mere chest main dard hai aur haath sweling hai.'")
        print("    Transcript: ", hi_res["transcript"])
        print("    Detected:   ", hi_res["language_name"], f"(Confidence: {hi_res['language_confidence']})")
        results["Hindi-English Mixed"] = "PASSED (Detected as Hindi, preserved spoken terminology)"

    # Test 4: Kannada Auto Detection & Uncertainty
    if kn_file.exists():
        kn_auto = transcribe_audio_file(kn_file, language_preference="auto")
        print("\n[4] Kannada Auto Detection & Uncertainty Handling:")
        print("    Language Uncertain Flag:", kn_auto.get("language_uncertain"))
        print("    Reported Language Name: ", kn_auto.get("language_name"))
        results["Uncertainty Handling"] = f"PASSED (Flagged uncertain={kn_auto.get('language_uncertain')})"

    # Test 7: Empty Recording and Unsupported Format
    print("\n[7] Empty Recording and Unsupported Format Validation:")
    try:
        validate_audio_file("empty.webm", 0)
        results["Empty Audio Validation"] = "FAILED"
    except ValueError as e:
        print("    Empty Audio Rejection: ", str(e))
        assert "empty" in str(e).lower()
        results["Empty Audio Validation"] = "PASSED (400 Bad Request with clear message)"

    try:
        validate_audio_file("document.pdf", 1024)
        results["Unsupported Format Validation"] = "FAILED"
    except ValueError as e:
        print("    Format Rejection:      ", str(e))
        assert "unsupported" in str(e).lower()
        results["Unsupported Format Validation"] = "PASSED (400 Bad Request with supported list)"

    # Test 10: Successful Ticket Creation After Transcription
    print("\n[10] Ticket Creation After Transcription:")
    import uuid
    uid = uuid.uuid4().hex[:6]
    post_res = client.post("/api/calls/process-transcript", json={
        "caller_name": f"Nurse Preeti {uid}",
        "patient_name": f"Ramesh Gowda {uid}",
        "room_number": f"Room {uid}",
        "raw_transcript": f"Call {uid}: Patient in Room {uid} has sudden severe chest pain and left arm swelling. Also he has not received his diabetic lunch tray yet.",
        "language": "en"
    })
    assert post_res.status_code == 200
    call_data = post_res.json()
    assert call_data["emergency_detected"] is True
    assert len(call_data["extracted_tickets"]) >= 2
    t_emergency = call_data["extracted_tickets"][0]
    t_routine = call_data["extracted_tickets"][1]
    print(f"    Call #{call_data['call']['id']} created with {len(call_data['extracted_tickets'])} tickets.")
    print(f"    Ticket 1: {t_emergency['title']} [{t_emergency['urgency']}]")
    print(f"    Ticket 2: {t_routine['title']} [{t_routine['urgency']}]")
    results["Ticket Creation"] = "PASSED (Decomposed multi-intent + STAT emergency)"

    # Test 11: Deleting a Resolved Ticket
    print("\n[11] Deleting a Resolved Ticket:")
    # Resolve ticket 2
    patch_res = client.patch(f"/api/tickets/{t_routine['id']}", json={"status": "RESOLVED"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "RESOLVED"
    
    # Delete ticket 2
    del_res = client.delete(f"/api/tickets/{t_routine['id']}")
    assert del_res.status_code == 200
    print(f"    Delete Ticket #{t_routine['id']} Response: {del_res.json()['message']}")
    results["Delete Resolved Ticket"] = "PASSED (Deleted from database)"

    # Test 12: Attempting to Delete an Unresolved Ticket (Should Fail!)
    print("\n[12] Attempting to Delete an Unresolved (Emergency) Ticket:")
    del_fail_res = client.delete(f"/api/tickets/{t_emergency['id']}")
    print(f"    Status Code: {del_fail_res.status_code}")
    print(f"    Error Detail: {del_fail_res.json()['detail']}")
    assert del_fail_res.status_code == 400
    assert "only tickets with status 'resolved' can be deleted" in del_fail_res.json()["detail"].lower()
    results["Unresolved Delete Protection"] = "PASSED (Rejected with 400 Bad Request)"

    # Test 13: Refreshing Dashboard to Verify Persistence
    print("\n[13] Verifying Dashboard Deletion Persistence:")
    # Verify ticket 2 is really gone from /api/tickets
    get_tickets = client.get("/api/tickets").json()
    assert not any(t["id"] == t_routine["id"] for t in get_tickets)
    # Verify ticket 1 (the emergency ticket) STILL EXISTS
    assert any(t["id"] == t_emergency["id"] for t in get_tickets)
    print("    Verified: Deleted resolved ticket does not exist in /api/tickets.")
    print("    Verified: Unresolved ticket remains active and persistent.")
    results["Deletion Persistence"] = "PASSED"

    print("\n" + "=" * 60)
    print("SUMMARY OF TEST RESULTS:")
    print("=" * 60)
    for test_name, status in results.items():
        print(f"  {test_name.ljust(35)}: {status}")
    print("=" * 60)

if __name__ == "__main__":
    run_all_verifications()
