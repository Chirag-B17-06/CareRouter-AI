"""Patient profiles, duplicate-safe matching, clinical records, medication integrity and
cross-patient isolation. All people and data below are fictional."""
from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from models_care import AuditEvent, Medication
from patient_matching import find_candidates, name_similarity, phonetic_key

pytestmark = pytest.mark.real_auth


def new_patient(care, user, **kw):
    body = {"full_name": "Akshay Kumar", "date_of_birth": "1984-05-12", "phone": "+91 98450 11122", **kw}
    return care.client.post("/api/patients", headers=user.headers, json=body)


# ------------------------------------------------------------------ profiles
def test_create_search_and_view_patient(care):
    nurse = care.make_user("nurse")
    res = new_patient(care, nurse, mrn="MRN-1001")
    assert res.status_code == 201
    p = res.json()
    assert p["patient_uid"] and len(p["patient_uid"]) == 32 and p["identity_verified"] is False
    found = care.client.get("/api/patients?q=akshay", headers=nurse.headers).json()
    assert found["total"] == 1 and found["items"][0]["id"] == p["id"]
    assert care.client.get("/api/patients?q=MRN-1001", headers=nurse.headers).json()["total"] == 1
    assert care.client.get("/api/patients?q=nobody", headers=nurse.headers).json()["total"] == 0
    assert care.client.get(f"/api/patients/{p['id']}", headers=nurse.headers).status_code == 200


def test_search_is_paginated(care):
    nurse = care.make_user("nurse")
    for i in range(5):
        new_patient(care, nurse, full_name=f"Patient Number{chr(65 + i)} Rao", date_of_birth=f"19{70 + i}-01-01",
                    phone=f"90000000{i}0", confirm_not_duplicate=True)
    page = care.client.get("/api/patients?q=rao&page=2&page_size=2", headers=nurse.headers).json()
    assert page["total"] == 5 and len(page["items"]) == 2 and page["page"] == 2


def test_validation_rejects_implausible_input(care):
    nurse = care.make_user("nurse")
    assert new_patient(care, nurse, date_of_birth="2999-01-01").status_code == 422
    assert new_patient(care, nurse, email="not-an-email").status_code == 422
    assert new_patient(care, nurse, contact_preference="carrier-pigeon").status_code == 422
    assert new_patient(care, nurse, full_name="A").status_code == 422


def test_mrn_is_unique(care):
    nurse = care.make_user("nurse")
    assert new_patient(care, nurse, mrn="MRN-7").status_code == 201
    dup = new_patient(care, nurse, full_name="Completely Different", date_of_birth="1999-09-09",
                      phone="9111111111", mrn="MRN-7", confirm_not_duplicate=True)
    assert dup.status_code == 409


def test_editing_the_name_requires_identity_reverification(care):
    nurse, clin = care.make_user("nurse"), care.make_user("clinician")
    pid = new_patient(care, nurse).json()["id"]
    assert care.client.post(f"/api/patients/{pid}/verify", headers=nurse.headers).status_code == 403
    assert care.client.post(f"/api/patients/{pid}/verify", headers=clin.headers).json()["identity_verified"] is True
    edited = care.client.patch(f"/api/patients/{pid}", headers=nurse.headers, json={"full_name": "Akshay K Kumar"})
    assert edited.json()["identity_verified"] is False


# ------------------------------------------------------------------ matching / duplicates
def test_similar_spellings_are_matched_but_never_equal_certainty():
    assert name_similarity("Akshay Kumar", "Akshai Kumar") >= 0.88
    assert name_similarity("Mohammed Ali", "Muhammad Ali") >= 0.85
    assert name_similarity("Akshay", "Priya Nair") < 0.5
    assert phonetic_key("Mohammed") == phonetic_key("Muhammad")


def test_duplicate_creation_is_blocked_until_confirmed(care):
    nurse = care.make_user("nurse")
    assert new_patient(care, nurse).status_code == 201
    typo = new_patient(care, nurse, full_name="Akshai Kumar")          # same person, different spelling
    assert typo.status_code == 409
    candidates = typo.json()["detail"]["candidates"]
    assert candidates and candidates[0]["display_name"] == "Akshay Kumar"
    forced = new_patient(care, nurse, full_name="Akshai Kumar", date_of_birth="1990-02-02",
                         phone="9222222222", confirm_not_duplicate=True)
    assert forced.status_code == 201
    with care.Session() as db:
        assert db.query(AuditEvent).filter(AuditEvent.action == "patient_created").count() == 2


def test_different_dob_is_a_conflict_signal_not_a_match(care):
    nurse = care.make_user("nurse")
    new_patient(care, nurse)
    twin = new_patient(care, nurse, date_of_birth="1960-01-01", phone="9333333333")   # same name, other person
    assert twin.status_code == 201


def test_name_only_match_is_low_confidence_and_never_auto_linked(care):
    nurse = care.make_user("nurse")
    pid = new_patient(care, nurse).json()["id"]
    body = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": "Patient Akshay Kumar, age 41, wants a billing statement.", "language": "en"}).json()
    assert body["call"]["patient_id"] is None
    assert body["call"]["patient_match_status"] == "needs_confirmation"
    cand = body["patient_match_candidates"][0]
    assert cand["patient_id"] == pid and cand["confidence_band"] in ("medium", "low")
    assert all(t["patient_id"] is None for t in body["extracted_tickets"])
    # candidates are retrievable for the review screen
    listed = care.client.get(f"/api/conversations/{body['call']['id']}/patient-candidates", headers=nurse.headers)
    assert listed.json()[0]["patient_id"] == pid


def test_human_confirmation_links_conversation_and_tasks(care):
    nurse = care.make_user("nurse")
    pid = new_patient(care, nurse).json()["id"]
    body = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": "Patient Akshay Kumar wants a billing statement. Please reschedule his appointment. The insurance claim is pending.", "language": "en"}).json()
    cid = body["call"]["id"]
    ok = care.client.post(f"/api/conversations/{cid}/link-patient", headers=nurse.headers, json={"patient_id": pid})
    assert ok.status_code == 200
    call = care.client.get(f"/api/calls/{cid}", headers=nurse.headers).json()
    assert call["patient_id"] == pid and call["patient_match_status"] == "confirmed"
    assert all(t["patient_id"] == pid for t in call["tickets"])
    timeline = care.client.get(f"/api/patients/{pid}/timeline", headers=nurse.headers).json()
    assert len(timeline["conversations"]) == 1 and len(timeline["tasks"]) >= 2
    assert "raw_transcript" not in timeline["conversations"][0]          # summaries only
    care.client.post(f"/api/conversations/{cid}/unlink-patient", headers=nurse.headers)
    assert care.client.get(f"/api/patients/{pid}/timeline", headers=nurse.headers).json()["tasks"] == []
    assert care.client.post(f"/api/conversations/{cid}/link-patient", headers=nurse.headers,
                            json={"patient_id": 99999}).status_code == 404


def test_staff_selected_patient_is_linked_immediately(care):
    nurse = care.make_user("nurse")
    pid = new_patient(care, nurse).json()["id"]
    body = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": "Room 5 needs a dressing change.", "language": "en", "patient_id": pid}).json()
    assert body["call"]["patient_match_status"] == "confirmed"
    assert care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": "Room 6 needs water.", "patient_id": 424242}).status_code == 404


def test_identifier_match_is_high_confidence_but_still_needs_confirmation(care):
    nurse = care.make_user("nurse")
    pid = new_patient(care, nurse, mrn="AB-10293").json()["id"]
    with care.Session() as db:
        cands = find_candidates(db, mrn="AB-10293")
        assert cands[0].patient_id == pid and cands[0].confidence_band == "high" and "mrn_exact" in cands[0].signals
    body = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": "Patient Akshay Kumar, MRN AB-10293, needs a dressing change.", "language": "en"}).json()
    assert body["call"]["patient_match_status"] == "needs_confirmation"
    assert body["patient_match_candidates"][0]["confidence_band"] == "high"


def test_unknown_patient_yields_no_candidates(care):
    nurse = care.make_user("nurse")
    body = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": "Patient Zubin Mehta needs a dressing change.", "language": "en"}).json()
    assert body["call"]["patient_match_status"] == "none" and body["patient_match_candidates"] == []


# ------------------------------------------------------------------ cross-patient isolation
def test_patient_cannot_read_any_other_patient_or_staff_data(care):
    a, b = care.make_patient("Alpha Patient"), care.make_patient("Beta Patient")
    ua = care.make_user("patient", patient=a)
    for path in (f"/api/patients/{b.id}", f"/api/patients/{a.id}", f"/api/patients/{b.id}/medications",
                 f"/api/patients/{b.id}/clinical", f"/api/patients/{b.id}/timeline", "/api/patients"):
        assert care.client.get(path, headers=ua.headers).status_code == 403, path
    me = care.client.get("/api/portal/me", headers=ua.headers)
    assert me.status_code == 200 and me.json()["full_name"] == "Alpha Patient"


def test_staff_accounts_cannot_use_the_patient_portal(care):
    nurse = care.make_user("nurse")
    for path in ("/api/portal/me", "/api/portal/appointments", "/api/portal/requests", "/api/portal/slots"):
        assert care.client.get(path, headers=nurse.headers).status_code == 403


def test_assert_patient_access_hides_existence(care):
    from auth import assert_patient_access
    from fastapi import HTTPException
    a, b = care.make_patient("A One"), care.make_patient("B Two")
    ua = care.make_user("patient", patient=a)
    with care.Session() as db:
        from models_care import User
        user = db.get(User, ua.id)
        assert_patient_access(user, a.id)
        with pytest.raises(HTTPException) as exc:
            assert_patient_access(user, b.id)
        assert exc.value.status_code == 404


def test_patient_account_requires_a_profile(care):
    admin = care.make_user("admin")
    r = care.client.post("/api/auth/users", headers=admin.headers, json={
        "username": "orphan.pt", "password": "Another-Str0ng-Pass", "full_name": "X", "role": "patient"})
    assert r.status_code == 400
    p = care.make_patient("Linked One")
    r = care.client.post("/api/auth/users", headers=admin.headers, json={
        "username": "staff.with.patient", "password": "Another-Str0ng-Pass", "full_name": "X", "role": "nurse",
        "patient_id": p.id})
    assert r.status_code == 400


# ------------------------------------------------------------------ clinical records
def test_clinical_records_are_role_restricted_and_never_deleted(care):
    clin, nurse = care.make_user("clinician"), care.make_user("nurse")
    p = care.make_patient("Clinical Case")
    add = care.client.post(f"/api/patients/{p.id}/clinical", headers=clin.headers, json={
        "record_type": "allergy", "description": "Penicillin - rash", "severity": "moderate"})
    assert add.status_code == 201
    assert care.client.post(f"/api/patients/{p.id}/clinical", headers=nurse.headers,
                            json={"record_type": "allergy", "description": "x y"}).status_code == 403
    assert len(care.client.get(f"/api/patients/{p.id}/clinical", headers=nurse.headers).json()) == 1
    rid = add.json()["id"]
    flagged = care.client.post(f"/api/patients/{p.id}/clinical/{rid}/entered-in-error", headers=clin.headers)
    assert flagged.json()["entered_in_error"] is True
    assert len(care.client.get(f"/api/patients/{p.id}/clinical", headers=clin.headers).json()) == 1   # still there
    assert care.client.post(f"/api/patients/{p.id}/clinical", headers=clin.headers,
                            json={"record_type": "gossip", "description": "no"}).status_code == 422


# ------------------------------------------------------------------ medication integrity
MED = {
    "medicine": "Amoxicillin", "dose": "500 mg", "route": "oral", "frequency": "three times daily",
    "duration": "7 days", "prescriber_name": "Dr. Fictional Rao", "source": "clinician_entered",
    "effective_from": date.today().isoformat(), "attest_verified": True,
}


def test_only_authorised_roles_can_record_prescriptions(care):
    p = care.make_patient("Rx Patient")
    for role in ("nurse", "coordinator"):
        u = care.make_user(role)
        assert care.client.post(f"/api/patients/{p.id}/medications", headers=u.headers, json=MED).status_code == 403
    for role in ("clinician", "pharmacist"):
        u = care.make_user(role, department="Pharmacy & Therapeutics" if role == "pharmacist" else None)
        body = {**MED, "medicine": f"Drug-{role}"}
        assert care.client.post(f"/api/patients/{p.id}/medications", headers=u.headers, json=body).status_code == 201


def test_prescription_requires_attestation_and_all_fields(care):
    clin = care.make_user("clinician")
    p = care.make_patient("Rx Patient")
    no_attest = {**MED, "attest_verified": False}
    assert care.client.post(f"/api/patients/{p.id}/medications", headers=clin.headers, json=no_attest).status_code == 400
    for missing in ("dose", "route", "frequency", "prescriber_name", "effective_from"):
        body = {k: v for k, v in MED.items() if k != missing}
        assert care.client.post(f"/api/patients/{p.id}/medications", headers=clin.headers, json=body).status_code == 422, missing
    bad_dates = {**MED, "effective_to": (date.today() - timedelta(days=3)).isoformat()}
    assert care.client.post(f"/api/patients/{p.id}/medications", headers=clin.headers, json=bad_dates).status_code == 400
    with care.Session() as db:
        assert db.query(Medication).count() == 0


def test_prescription_is_never_silently_overwritten(care):
    clin = care.make_user("clinician")
    p = care.make_patient("Rx Patient")
    first = care.client.post(f"/api/patients/{p.id}/medications", headers=clin.headers, json=MED).json()
    # same drug again -> conflict, original untouched
    again = care.client.post(f"/api/patients/{p.id}/medications", headers=clin.headers, json={**MED, "dose": "1 g"})
    assert again.status_code == 409
    # there is no endpoint that edits a stored dose
    assert care.client.patch(f"/api/patients/{p.id}/medications/{first['id']}", headers=clin.headers,
                             json={"dose": "9 g"}).status_code in (404, 405)
    # a change is an explicit supersede that preserves history
    sup = care.client.post(f"/api/patients/{p.id}/medications/{first['id']}/supersede", headers=clin.headers,
                           json={**MED, "dose": "250 mg"})
    assert sup.status_code == 201 and sup.json()["supersedes_id"] == first["id"]
    active = care.client.get(f"/api/patients/{p.id}/medications", headers=clin.headers).json()
    assert [m["dose"] for m in active] == ["250 mg"]
    history = care.client.get(f"/api/patients/{p.id}/medications?include_history=true", headers=clin.headers).json()
    assert {m["dose"]: m["status"] for m in history} == {"500 mg": "superseded", "250 mg": "active"}
    # an already-superseded row cannot be superseded twice
    assert care.client.post(f"/api/patients/{p.id}/medications/{first['id']}/supersede", headers=clin.headers,
                            json={**MED, "dose": "100 mg"}).status_code == 409


def test_database_prevents_two_successors_and_bad_date_ranges(care):
    clin = care.make_user("clinician")
    p = care.make_patient("Rx Patient")
    first = care.client.post(f"/api/patients/{p.id}/medications", headers=clin.headers, json=MED).json()
    with care.Session() as db:
        def row(**kw):
            base = dict(patient_id=p.id, medicine="X", dose="1", route="oral", frequency="daily",
                        prescriber_name="Dr Y", source="clinician_entered", effective_from=date.today(),
                        verified_by_user_id=clin.id, status="active")
            base.update(kw)
            return Medication(**base)
        db.add(row(supersedes_id=first["id"]))
        db.flush()
        db.add(row(supersedes_id=first["id"]))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        db.add(row(effective_to=date.today() - timedelta(days=1)))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_stop_and_error_flows_and_patient_isolation(care):
    clin = care.make_user("clinician")
    p, other = care.make_patient("Rx Patient"), care.make_patient("Other Patient")
    m = care.client.post(f"/api/patients/{p.id}/medications", headers=clin.headers, json=MED).json()
    # a medication id belonging to one patient cannot be reached through another patient's URL
    assert care.client.post(f"/api/patients/{other.id}/medications/{m['id']}/stop", headers=clin.headers,
                            json={"effective_to": date.today().isoformat()}).status_code == 404
    stopped = care.client.post(f"/api/patients/{p.id}/medications/{m['id']}/stop", headers=clin.headers,
                               json={"effective_to": date.today().isoformat()})
    assert stopped.json()["status"] == "stopped"
    assert care.client.post(f"/api/patients/{p.id}/medications/{m['id']}/stop", headers=clin.headers,
                            json={"effective_to": date.today().isoformat()}).status_code == 409
    assert care.client.get(f"/api/patients/{p.id}/medications", headers=clin.headers).json() == []


def test_medication_access_is_audited_without_clinical_text(care):
    clin, admin = care.make_user("clinician"), care.make_user("admin")
    p = care.make_patient("Rx Patient")
    care.client.post(f"/api/patients/{p.id}/medications", headers=clin.headers, json=MED)
    care.client.get(f"/api/patients/{p.id}/medications", headers=clin.headers)
    events = care.client.get(f"/api/audit/events?patient_id={p.id}", headers=admin.headers).json()["items"]
    assert {"medication_added", "medications_viewed"} <= {e["action"] for e in events}
    assert "Amoxicillin" not in str(events)
