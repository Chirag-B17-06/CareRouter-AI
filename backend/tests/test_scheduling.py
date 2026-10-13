"""Scheduling service and patient portal: availability, safe booking, concurrency, timezones,
patient isolation, change requests, reminders and follow-ups. Fictional data only."""
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from models_care import Appointment, AppointmentSlot, Notification
from scheduling import book_slot

pytestmark = pytest.mark.real_auth

IST = ZoneInfo("Asia/Kolkata")


def future_local(days=2, hour=10, minute=0):
    d = (datetime.now(IST) + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return d.replace(tzinfo=None).isoformat()          # naive => interpreted in hospital timezone


def setup_clinic(care, staff, count=3, department="Cardiology", location="Main Campus"):
    clin = care.client.post("/api/scheduling/clinicians", headers=staff.headers, json={
        "full_name": "Dr. Fictional Iyer", "department": department, "specialty": "Cardiologist", "location": location}).json()
    slots = care.client.post("/api/scheduling/slots", headers=staff.headers, json={
        "clinician_id": clin["id"], "start": future_local(), "duration_minutes": 20, "count": count})
    assert slots.status_code == 201, slots.text
    return clin, slots.json()


def portal_patient(care, name="Portal Patient One", **kw):
    p = care.make_patient(name, **kw)
    return p, care.make_user("patient", patient=p)


# ------------------------------------------------------------------ availability
def test_no_availability_is_invented(care):
    p, pu = portal_patient(care)
    assert care.client.get("/api/portal/slots", headers=pu.headers).json() == []
    assert care.client.get("/api/portal/directory", headers=pu.headers).json()["departments"] == []


def test_staff_create_slots_and_patients_see_only_open_future_ones(care):
    coord = care.make_user("coordinator", department="Outpatient & Appointment Coordination")
    clin, slots = setup_clinic(care, coord, count=3)
    assert len(slots) == 3 and slots[0]["clinician_name"] == "Dr. Fictional Iyer"
    p, pu = portal_patient(care)
    visible = care.client.get("/api/portal/slots", headers=pu.headers).json()
    assert len(visible) == 3
    booked = care.client.post("/api/portal/appointments", headers=pu.headers, json={"slot_id": slots[0]["id"]})
    assert booked.status_code == 201
    remaining = care.client.get("/api/portal/slots", headers=pu.headers).json()
    assert len(remaining) == 2 and slots[0]["id"] not in {s["id"] for s in remaining}


def test_search_by_department_clinician_location_and_date(care):
    coord = care.make_user("coordinator")
    c1, _ = setup_clinic(care, coord, department="Cardiology", location="Main Campus")
    c2 = care.client.post("/api/scheduling/clinicians", headers=coord.headers, json={
        "full_name": "Dr. Fictional Das", "department": "Orthopaedics", "location": "North Wing"}).json()
    care.client.post("/api/scheduling/slots", headers=coord.headers,
                     json={"clinician_id": c2["id"], "start": future_local(days=4), "count": 2})
    p, pu = portal_patient(care)
    h = pu.headers
    assert len(care.client.get("/api/portal/slots?department=Orthopaedics", headers=h).json()) == 2
    assert len(care.client.get(f"/api/portal/slots?clinician_id={c1['id']}", headers=h).json()) == 3
    assert len(care.client.get("/api/portal/slots?location=North Wing", headers=h).json()) == 2
    day = (datetime.now(IST) + timedelta(days=4)).date().isoformat()
    assert len(care.client.get(f"/api/portal/slots?date_from={day}&date_to={day}", headers=h).json()) == 2
    d = care.client.get("/api/portal/directory", headers=h).json()
    assert d["departments"] == ["Cardiology", "Orthopaedics"] and len(d["clinicians"]) == 2


def test_slot_rules_future_only_and_no_overlap(care):
    coord = care.make_user("coordinator")
    clin, _ = setup_clinic(care, coord, count=1)
    past = (datetime.now(IST) - timedelta(hours=2)).replace(tzinfo=None).isoformat()
    assert care.client.post("/api/scheduling/slots", headers=coord.headers,
                            json={"clinician_id": clin["id"], "start": past}).status_code == 400
    overlap = care.client.post("/api/scheduling/slots", headers=coord.headers,
                               json={"clinician_id": clin["id"], "start": future_local(minute=10), "duration_minutes": 20})
    assert overlap.status_code == 409
    nurse = care.make_user("nurse")        # nurses may view but patients/others may not create slots
    p, pu = portal_patient(care)
    assert care.client.post("/api/scheduling/slots", headers=pu.headers,
                            json={"clinician_id": clin["id"], "start": future_local(days=5)}).status_code == 403


def test_hospital_timezone_is_used_for_input_and_output(care):
    coord = care.make_user("coordinator")
    clin = care.client.post("/api/scheduling/clinicians", headers=coord.headers, json={
        "full_name": "Dr. Fictional Zone", "department": "General Medicine", "location": "Main"}).json()
    slot = care.client.post("/api/scheduling/slots", headers=coord.headers,
                            json={"clinician_id": clin["id"], "start": future_local(hour=9)}).json()[0]
    assert slot["start_local"].endswith("+05:30") and "T09:00:00" in slot["start_local"]
    assert slot["start_utc"].endswith("Z") or "+00:00" in slot["start_utc"]
    assert "T03:30:00" in slot["start_utc"]                      # 09:00 IST == 03:30 UTC
    explicit = care.client.post("/api/scheduling/slots", headers=coord.headers, json={
        "clinician_id": clin["id"], "start": (datetime.now(timezone.utc) + timedelta(days=6)).replace(
            hour=0, minute=0, second=0, microsecond=0).isoformat()}).json()[0]
    assert "T05:30:00+05:30" in explicit["start_local"]          # explicit UTC offset honoured


# ------------------------------------------------------------------ booking
def test_booking_confirms_only_after_reservation_and_notifies(care):
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord)
    p, pu = portal_patient(care)
    res = care.client.post("/api/portal/appointments", headers=pu.headers,
                           json={"slot_id": slots[0]["id"], "reason": "Chest check-up", "idempotency_key": "k1"})
    assert res.status_code == 201
    appt = res.json()
    assert appt["status"] == "confirmed" and appt["slot"]["id"] == slots[0]["id"]
    with care.Session() as db:
        assert db.get(AppointmentSlot, slots[0]["id"]).status == "booked"
        kinds = {(n.channel, n.kind, n.status) for n in db.query(Notification).filter(Notification.patient_id == p.id)}
        assert ("in_app", "booking_confirmation", "sent") in kinds
        assert ("in_app", "reminder", "pending") in kinds           # reminder scheduled ahead of time
    notes = care.client.get("/api/portal/notifications", headers=pu.headers).json()
    assert [n["kind"] for n in notes] == ["booking_confirmation"]    # reminder not shown before its time


def test_sms_reminders_stay_pending_until_a_provider_exists(care):
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord)
    p, pu = portal_patient(care, contact_preference="sms")
    care.client.post("/api/portal/appointments", headers=pu.headers, json={"slot_id": slots[0]["id"]})
    with care.Session() as db:
        sms = db.query(Notification).filter(Notification.channel == "sms").all()
        assert sms and all(n.status == "pending" and n.sent_at is None for n in sms)   # never faked as 'sent'


def test_booking_unknown_or_past_slot_and_double_booking_rejected(care):
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord)
    (p1, u1), (p2, u2) = portal_patient(care, "Patient Alpha"), portal_patient(care, "Patient Beta")
    assert care.client.post("/api/portal/appointments", headers=u1.headers, json={"slot_id": 9999}).status_code == 404
    assert care.client.post("/api/portal/appointments", headers=u1.headers, json={"slot_id": slots[0]["id"]}).status_code == 201
    clash = care.client.post("/api/portal/appointments", headers=u2.headers, json={"slot_id": slots[0]["id"]})
    assert clash.status_code == 409 and "no longer available" in clash.json()["detail"]
    with care.Session() as db:
        assert db.query(Appointment).filter(Appointment.slot_id == slots[0]["id"]).count() == 1
        past = AppointmentSlot(clinician_id=slots[0]["clinician_id"], status="open",
                               start_utc=datetime.utcnow() - timedelta(hours=1),
                               end_utc=datetime.utcnow() - timedelta(minutes=40))
        db.add(past)
        db.commit()
        past_id = past.id
    assert care.client.post("/api/portal/appointments", headers=u2.headers, json={"slot_id": past_id}).status_code == 409


def test_booking_is_idempotent(care):
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord)
    p, pu = portal_patient(care)
    body = {"slot_id": slots[0]["id"], "idempotency_key": "double-click"}
    a = care.client.post("/api/portal/appointments", headers=pu.headers, json=body)
    b = care.client.post("/api/portal/appointments", headers=pu.headers, json=body)
    assert a.status_code == b.status_code == 201 and a.json()["id"] == b.json()["id"]
    with care.Session() as db:
        assert db.query(Appointment).count() == 1


def test_concurrent_booking_of_one_slot_has_exactly_one_winner(care_file):
    care = care_file
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord, count=1)
    slot_id = slots[0]["id"]
    patients = [care.make_patient(f"Racer Number{chr(65 + i)}") for i in range(12)]
    results, barrier = [], threading.Barrier(len(patients))

    class Actor:
        id = None
        role = "patient"

    def worker(patient):
        db = care.Session()
        try:
            barrier.wait()
            book_slot(db, patient_id=patient.id, slot_id=slot_id, reason=None, idempotency_key=None,
                      source="portal", actor=Actor())
            results.append("won")
        except HTTPException as exc:
            results.append(exc.status_code)
        finally:
            db.close()

    threads = [threading.Thread(target=worker, args=(p,)) for p in patients]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert results.count("won") == 1 and results.count(409) == len(patients) - 1, results
    with care.Session() as db:
        live = db.query(Appointment).filter(Appointment.slot_id == slot_id, Appointment.status.in_(("pending", "confirmed"))).count()
        assert live == 1 and db.get(AppointmentSlot, slot_id).status == "booked"


def test_database_constraint_alone_blocks_a_second_live_appointment(care):
    from sqlalchemy.exc import IntegrityError
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord, count=1)
    p1, p2 = care.make_patient("Constraint One"), care.make_patient("Constraint Two")
    with care.Session() as db:
        db.add(Appointment(patient_id=p1.id, slot_id=slots[0]["id"], department="Cardiology", status="confirmed"))
        db.flush()
        db.add(Appointment(patient_id=p2.id, slot_id=slots[0]["id"], department="Cardiology", status="pending"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_staff_can_book_for_a_patient_and_pending_mode_requires_confirmation(care, monkeypatch):
    monkeypatch.setenv("APPOINTMENT_AUTO_CONFIRM", "false")
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord)
    p = care.make_patient("Staff Booked")
    res = care.client.post("/api/scheduling/appointments", headers=coord.headers,
                           json={"patient_id": p.id, "slot_id": slots[0]["id"]})
    assert res.status_code == 201 and res.json()["status"] == "pending"
    appt_id = res.json()["id"]
    confirmed = care.client.post(f"/api/scheduling/appointments/{appt_id}/confirm", headers=coord.headers)
    assert confirmed.json()["status"] == "confirmed"
    done = care.client.post(f"/api/scheduling/appointments/{appt_id}/complete", headers=coord.headers)
    assert done.json()["status"] == "completed"
    assert care.client.post(f"/api/scheduling/appointments/{appt_id}/cancel", headers=coord.headers).status_code == 409


def test_cancellation_releases_the_slot(care):
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord)
    p = care.make_patient("Cancel Me")
    appt = care.client.post("/api/scheduling/appointments", headers=coord.headers,
                            json={"patient_id": p.id, "slot_id": slots[0]["id"]}).json()
    assert care.client.post(f"/api/scheduling/appointments/{appt['id']}/cancel", headers=coord.headers).json()["status"] == "cancelled"
    with care.Session() as db:
        assert db.get(AppointmentSlot, slots[0]["id"]).status == "open"
    p2, u2 = portal_patient(care, "Next In Line")
    assert care.client.post("/api/portal/appointments", headers=u2.headers, json={"slot_id": slots[0]["id"]}).status_code == 201


# ------------------------------------------------------------------ patient isolation
def test_patient_sees_and_changes_only_their_own_appointments(care):
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord)
    (p1, u1), (p2, u2) = portal_patient(care, "Isolated One"), portal_patient(care, "Isolated Two")
    a1 = care.client.post("/api/portal/appointments", headers=u1.headers, json={"slot_id": slots[0]["id"]}).json()
    care.client.post("/api/portal/appointments", headers=u2.headers, json={"slot_id": slots[1]["id"]})
    mine = care.client.get("/api/portal/appointments?scope=all", headers=u1.headers).json()
    assert [a["id"] for a in mine] == [a1["id"]] and all(a["patient_id"] == p1.id for a in mine)
    # another patient's appointment id behaves exactly like a nonexistent one
    probe = care.client.post(f"/api/portal/appointments/{a1['id']}/request-change", headers=u2.headers,
                             json={"request_type": "cancel"})
    ghost = care.client.post("/api/portal/appointments/99999/request-change", headers=u2.headers,
                             json={"request_type": "cancel"})
    assert probe.status_code == ghost.status_code == 404 and probe.json() == ghost.json()
    assert care.client.get("/api/scheduling/appointments", headers=u1.headers).status_code == 403
    assert care.client.get("/api/portal/notifications", headers=u2.headers).json() != []
    with care.Session() as db:
        theirs = {n.id for n in db.query(Notification).filter(Notification.patient_id == p1.id)}
    seen_by_u2 = {n["id"] for n in care.client.get("/api/portal/notifications", headers=u2.headers).json()}
    assert theirs and not (theirs & seen_by_u2)


def test_upcoming_vs_past_views(care):
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord)
    p, pu = portal_patient(care)
    a = care.client.post("/api/portal/appointments", headers=pu.headers, json={"slot_id": slots[0]["id"]}).json()
    assert len(care.client.get("/api/portal/appointments?scope=upcoming", headers=pu.headers).json()) == 1
    assert care.client.get("/api/portal/appointments?scope=past", headers=pu.headers).json() == []
    care.client.post(f"/api/scheduling/appointments/{a['id']}/cancel", headers=coord.headers)
    assert care.client.get("/api/portal/appointments?scope=upcoming", headers=pu.headers).json() == []
    assert len(care.client.get("/api/portal/appointments?scope=past", headers=pu.headers).json()) == 1


# ------------------------------------------------------------------ change requests
def test_change_request_creates_task_and_staff_resolves_reschedule(care):
    coord = care.make_user("coordinator", department="Outpatient & Appointment Coordination")
    _, slots = setup_clinic(care, coord)
    p, pu = portal_patient(care)
    a = care.client.post("/api/portal/appointments", headers=pu.headers, json={"slot_id": slots[0]["id"]}).json()
    req = care.client.post(f"/api/portal/appointments/{a['id']}/request-change", headers=pu.headers,
                           json={"request_type": "reschedule", "note": "Prefer afternoon"})
    assert req.status_code == 200 and req.json()["change_request"] == "reschedule"
    assert care.client.post(f"/api/portal/appointments/{a['id']}/request-change", headers=pu.headers,
                            json={"request_type": "cancel"}).status_code == 409
    tasks = care.client.get(f"/api/tickets?patient_id={p.id}", headers=coord.headers).json()
    assert tasks and tasks[0]["assigned_team"] == "Outpatient & Appointment Coordination"
    # staff approves into slot #3; slot #1 is released
    res = care.client.post(f"/api/scheduling/appointments/{a['id']}/resolve-change", headers=coord.headers,
                           json={"action": "approve", "new_slot_id": slots[2]["id"]})
    assert res.status_code == 200 and res.json()["slot"]["id"] == slots[2]["id"] and res.json()["change_request"] is None
    with care.Session() as db:
        assert db.get(AppointmentSlot, slots[0]["id"]).status == "open"
        assert db.get(AppointmentSlot, slots[2]["id"]).status == "booked"


def test_cancel_request_and_rejection_paths(care):
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord)
    p, pu = portal_patient(care)
    a = care.client.post("/api/portal/appointments", headers=pu.headers, json={"slot_id": slots[0]["id"]}).json()
    care.client.post(f"/api/portal/appointments/{a['id']}/request-change", headers=pu.headers, json={"request_type": "cancel"})
    rej = care.client.post(f"/api/scheduling/appointments/{a['id']}/resolve-change", headers=coord.headers, json={"action": "reject"})
    assert rej.json()["status"] == "confirmed" and rej.json()["change_request"] is None
    care.client.post(f"/api/portal/appointments/{a['id']}/request-change", headers=pu.headers, json={"request_type": "cancel"})
    ok = care.client.post(f"/api/scheduling/appointments/{a['id']}/resolve-change", headers=coord.headers, json={"action": "approve"})
    assert ok.json()["status"] == "cancelled"
    # reschedule into a slot someone else holds is refused
    p2, u2 = portal_patient(care, "Other Holder")
    a2 = care.client.post("/api/portal/appointments", headers=u2.headers, json={"slot_id": slots[1]["id"]}).json()
    p3, u3 = portal_patient(care, "Third Person")
    a3 = care.client.post("/api/portal/appointments", headers=u3.headers, json={"slot_id": slots[2]["id"]}).json()
    care.client.post(f"/api/portal/appointments/{a3['id']}/request-change", headers=u3.headers, json={"request_type": "reschedule"})
    taken = care.client.post(f"/api/scheduling/appointments/{a3['id']}/resolve-change", headers=coord.headers,
                             json={"action": "approve", "new_slot_id": slots[1]["id"]})
    assert taken.status_code == 409
    with care.Session() as db:
        assert db.get(Appointment, a3["id"]).slot_id == slots[2]["id"]       # unchanged
        assert db.get(AppointmentSlot, slots[2]["id"]).status == "booked"


# ------------------------------------------------------------------ follow-ups & routine requests
def test_follow_up_instructions_need_clinician_approval_before_patient_sees_them(care):
    nurse, clin = care.make_user("nurse"), care.make_user("clinician")
    p, pu = portal_patient(care)
    fu = care.client.post("/api/scheduling/follow-ups", headers=nurse.headers, json={
        "patient_id": p.id, "instruction": "Keep the dressing dry for 48 hours."})
    assert fu.status_code == 201 and fu.json()["visible_to_patient"] is False
    assert care.client.get("/api/portal/follow-ups", headers=pu.headers).json() == []
    assert care.client.post(f"/api/scheduling/follow-ups/{fu.json()['id']}/approve", headers=nurse.headers).status_code == 403
    care.client.post(f"/api/scheduling/follow-ups/{fu.json()['id']}/approve", headers=clin.headers)
    shown = care.client.get("/api/portal/follow-ups", headers=pu.headers).json()
    assert shown and shown[0]["instruction"].startswith("Keep the dressing dry")
    other, ou = portal_patient(care, "Someone Else")
    assert care.client.get("/api/portal/follow-ups", headers=ou.headers).json() == []


def test_routine_request_becomes_a_routed_task_with_patient_friendly_status(care):
    coord = care.make_user("coordinator", department="Patient Billing & Accounts")
    p, pu = portal_patient(care)
    res = care.client.post("/api/portal/requests", headers=pu.headers, json={
        "request_type": "billing", "message": "Please email me last month's invoice.", "idempotency_key": "r1"})
    assert res.status_code == 201
    again = care.client.post("/api/portal/requests", headers=pu.headers, json={
        "request_type": "billing", "message": "Please email me last month's invoice.", "idempotency_key": "r1"})
    assert again.json()["id"] == res.json()["id"]
    listed = care.client.get("/api/portal/requests", headers=pu.headers).json()
    assert len(listed) == 1 and listed[0]["status"] == "Received"
    tasks = care.client.get(f"/api/tickets?patient_id={p.id}", headers=coord.headers).json()
    assert len(tasks) == 1 and tasks[0]["assigned_team"] == "Patient Billing & Accounts"
    care.client.post(f"/api/tickets/{tasks[0]['id']}/resolve", headers=coord.headers,
                     json={"resolution_notes": "Invoice emailed."})
    assert care.client.get("/api/portal/requests", headers=pu.headers).json()[0]["status"] == "Completed"
    other, ou = portal_patient(care, "Not Mine")
    assert care.client.get("/api/portal/requests", headers=ou.headers).json() == []
    assert care.client.post("/api/portal/requests", headers=pu.headers,
                            json={"request_type": "bogus", "message": "hello there"}).status_code == 422


def test_staff_overview_counts(care):
    coord = care.make_user("coordinator")
    _, slots = setup_clinic(care, coord, count=3)
    p, pu = portal_patient(care)
    a = care.client.post("/api/portal/appointments", headers=pu.headers, json={"slot_id": slots[0]["id"]}).json()
    care.client.post(f"/api/portal/appointments/{a['id']}/request-change", headers=pu.headers, json={"request_type": "cancel"})
    ov = care.client.get("/api/scheduling/overview", headers=coord.headers).json()
    assert ov["by_status"]["confirmed"] == 1 and ov["open_slots"] == 2 and ov["pending_change_requests"] == 1
    page = care.client.get("/api/scheduling/appointments?change_requested=true&page_size=5", headers=coord.headers).json()
    assert page["total"] == 1 and page["items"][0]["id"] == a["id"]
