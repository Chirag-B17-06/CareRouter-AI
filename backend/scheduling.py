"""Internal scheduling service, staff API and patient portal API.

No external scheduling integration exists in this project, so this is a real, internally
modelled scheduler.  Availability is only what staff/an integration have created as slots;
nothing is ever generated on the fly.

Double-booking protection (defence in depth):
  1. ``UPDATE appointment_slots SET status='booked' WHERE id=:id AND status='open'`` - an atomic
     compare-and-set; exactly one concurrent caller sees ``rowcount == 1``.
  2. A partial UNIQUE index on ``appointments(slot_id)`` for live statuses.
  3. Everything happens in one transaction: the appointment is only confirmed if the slot was won.
"""
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from audit import record_audit
from auth import assert_patient_access, require_patient_portal, require_permission
from config import get_settings
from database import Ticket, get_db
from models_care import (
    ACTIVE_APPOINTMENT_STATUSES, Appointment, AppointmentSlot, Clinician, FollowUpInstruction, Notification,
    Patient, PatientRequest, User, utcnow,
)
from tasks_service import TERMINAL_STATUSES, create_ticket

staff_router = APIRouter(prefix="/api/scheduling", tags=["scheduling"])
portal_router = APIRouter(prefix="/api/portal", tags=["patient-portal"])


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------
def hospital_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().hospital_timezone)


def to_utc_naive(value: datetime) -> datetime:
    """Naive input is interpreted in the hospital timezone; stored as naive UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=hospital_tz())
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def local_iso(value: datetime) -> str:
    return as_utc(value).astimezone(hospital_tz()).isoformat()


class SlotUnavailable(Exception):
    pass


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ClinicianIn(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    department: str = Field(..., min_length=2, max_length=100)
    specialty: Optional[str] = Field(None, max_length=100)
    location: str = Field(..., min_length=2, max_length=120)


class ClinicianOut(ClinicianIn):
    id: int
    is_active: bool


class SlotIn(BaseModel):
    clinician_id: int
    start: datetime
    duration_minutes: int = Field(20, ge=5, le=240)
    count: int = Field(1, ge=1, le=40, description="Create this many consecutive slots")


class SlotOut(BaseModel):
    id: int
    clinician_id: int
    clinician_name: str
    department: str
    specialty: Optional[str]
    location: str
    start_local: str
    end_local: str
    start_utc: datetime
    status: str


class BookRequest(BaseModel):
    slot_id: int
    reason: Optional[str] = Field(None, max_length=300)
    idempotency_key: Optional[str] = Field(None, max_length=100)


class StaffBookRequest(BookRequest):
    patient_id: int


class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    status: str
    department: str
    reason: Optional[str]
    slot: Optional[SlotOut]
    change_request: Optional[str]
    change_request_note: Optional[str]
    created_at: datetime


class ChangeRequestIn(BaseModel):
    request_type: str = Field(..., pattern="^(reschedule|cancel)$")
    note: Optional[str] = Field(None, max_length=300)


class ResolveChangeIn(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    new_slot_id: Optional[int] = None


class PatientRequestIn(BaseModel):
    request_type: str = Field(..., pattern="^(general|billing|insurance|prescription|report_followup|complaint)$")
    message: str = Field(..., min_length=3, max_length=1500)
    idempotency_key: Optional[str] = Field(None, max_length=100)


class FollowUpIn(BaseModel):
    patient_id: int
    instruction: str = Field(..., min_length=3, max_length=2000)
    appointment_id: Optional[int] = None
    due_date: Optional[date] = None


def _slot_out(slot: AppointmentSlot) -> SlotOut:
    c = slot.clinician
    return SlotOut(
        id=slot.id, clinician_id=c.id, clinician_name=c.full_name, department=c.department,
        specialty=c.specialty, location=c.location, start_local=local_iso(slot.start_utc),
        end_local=local_iso(slot.end_utc), start_utc=as_utc(slot.start_utc), status=slot.status,
    )


def _appt_out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=a.id, patient_id=a.patient_id, status=a.status, department=a.department, reason=a.reason,
        slot=_slot_out(a.slot) if a.slot else None, change_request=a.change_request,
        change_request_note=a.change_request_note, created_at=a.created_at,
    )


# ---------------------------------------------------------------------------
# Core booking logic
# ---------------------------------------------------------------------------
def _queue_notifications(db: Session, appt: Appointment, slot: AppointmentSlot, kind: str) -> None:
    patient = db.get(Patient, appt.patient_id)
    when = local_iso(slot.start_utc) if slot else ""
    texts = {
        "booking_confirmation": f"Your appointment is confirmed for {when}.",
        "booking_pending": f"Your appointment request for {when} was received and is awaiting confirmation.",
        "cancellation": "Your appointment has been cancelled.",
    }
    # In-app is delivered by being readable through the portal. SMS/email stay 'pending' until a
    # delivery provider is wired up (not configured here) - they are never marked sent falsely.
    channels = ["in_app"] + ([patient.contact_preference] if patient.contact_preference in ("sms", "email") else [])
    for channel in channels:
        db.add(Notification(
            patient_id=appt.patient_id, appointment_id=appt.id, channel=channel, kind=kind,
            body=texts[kind], status="sent" if channel == "in_app" else "pending",
            sent_at=utcnow() if channel == "in_app" else None,
        ))
    if kind == "booking_confirmation" and slot:
        remind_at = slot.start_utc - timedelta(hours=get_settings().reminder_hours_before)
        if remind_at > utcnow().replace(tzinfo=None):
            for channel in channels:
                db.add(Notification(
                    patient_id=appt.patient_id, appointment_id=appt.id, channel=channel, kind="reminder",
                    body=f"Reminder: you have an appointment at {when}.", scheduled_for=remind_at, status="pending",
                ))


def book_slot(db: Session, *, patient_id: int, slot_id: int, reason: Optional[str], idempotency_key: Optional[str],
              source: str, actor: User, conversation_id: Optional[int] = None) -> Appointment:
    if idempotency_key:
        prior = db.query(Appointment).filter(
            Appointment.patient_id == patient_id, Appointment.idempotency_key == idempotency_key).first()
        if prior:
            return prior

    slot = db.query(AppointmentSlot).filter(AppointmentSlot.id == slot_id).first()
    if not slot or not slot.clinician.is_active:
        raise HTTPException(status_code=404, detail="Appointment slot not found")
    now = utcnow().replace(tzinfo=None)
    if slot.start_utc <= now:
        raise HTTPException(status_code=409, detail="That time has already passed")

    won = db.execute(
        update(AppointmentSlot)
        .where(AppointmentSlot.id == slot_id, AppointmentSlot.status == "open")
        .values(status="booked")
    ).rowcount
    if won != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This slot is no longer available. Please choose another time.")

    status = "confirmed" if get_settings().appointment_auto_confirm else "pending"
    appt = Appointment(
        patient_id=patient_id, slot_id=slot_id, department=slot.clinician.department, reason=reason, status=status,
        source=source, idempotency_key=idempotency_key, created_by_user_id=actor.id, conversation_id=conversation_id,
    )
    try:
        db.add(appt)
        db.flush()
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            prior = db.query(Appointment).filter(
                Appointment.patient_id == patient_id, Appointment.idempotency_key == idempotency_key).first()
            if prior:
                return prior
        raise HTTPException(status_code=409, detail="This slot is no longer available. Please choose another time.")
    _queue_notifications(db, appt, slot, "booking_confirmation" if status == "confirmed" else "booking_pending")
    record_audit(db, user=actor, action="appointment_booked", resource_type="appointment", resource_id=appt.id,
                 patient_id=patient_id, detail={"status": status, "source": source})
    db.commit()
    return appt


def release_slot(db: Session, slot_id: Optional[int]) -> None:
    if slot_id is not None:
        db.execute(update(AppointmentSlot).where(AppointmentSlot.id == slot_id, AppointmentSlot.status == "booked")
                   .values(status="open"))


def _cancel(db: Session, appt: Appointment, actor: User, reason: str) -> None:
    if appt.status in ("cancelled", "completed"):
        raise HTTPException(status_code=409, detail=f"A {appt.status} appointment cannot be cancelled")
    slot = appt.slot
    appt.status = "cancelled"
    appt.cancelled_at = utcnow()
    appt.cancelled_reason = reason[:300]
    appt.change_request = None
    release_slot(db, appt.slot_id)
    _queue_notifications(db, appt, slot, "cancellation")
    record_audit(db, user=actor, action="appointment_cancelled", resource_type="appointment",
                 resource_id=appt.id, patient_id=appt.patient_id)


# ---------------------------------------------------------------------------
# Slot listing (shared)
# ---------------------------------------------------------------------------
def _query_slots(db: Session, *, department, clinician_id, location, date_from, date_to, available_only=True):
    q = db.query(AppointmentSlot).join(Clinician).filter(Clinician.is_active.is_(True))
    if available_only:
        q = q.filter(AppointmentSlot.status == "open", AppointmentSlot.start_utc > utcnow().replace(tzinfo=None))
    if department:
        q = q.filter(Clinician.department == department)
    if clinician_id:
        q = q.filter(Clinician.id == clinician_id)
    if location:
        q = q.filter(Clinician.location == location)
    if date_from:
        q = q.filter(AppointmentSlot.start_utc >= to_utc_naive(datetime.combine(date_from, datetime.min.time())))
    if date_to:
        q = q.filter(AppointmentSlot.start_utc < to_utc_naive(datetime.combine(date_to + timedelta(days=1), datetime.min.time())))
    return q.order_by(AppointmentSlot.start_utc)


# ---------------------------------------------------------------------------
# Staff API
# ---------------------------------------------------------------------------
@staff_router.post("/clinicians", response_model=ClinicianOut, status_code=201)
def create_clinician(payload: ClinicianIn, user: User = Depends(require_permission("appointment:manage")),
                     db: Session = Depends(get_db)):
    c = Clinician(**payload.model_dump())
    db.add(c)
    db.flush()
    record_audit(db, user=user, action="clinician_created", resource_type="clinician", resource_id=c.id)
    db.commit()
    return ClinicianOut(id=c.id, is_active=c.is_active, **payload.model_dump())


@staff_router.get("/clinicians", response_model=List[ClinicianOut])
def list_clinicians(department: Optional[str] = None, location: Optional[str] = None,
                    user: User = Depends(require_permission("task:read")), db: Session = Depends(get_db)):
    q = db.query(Clinician).filter(Clinician.is_active.is_(True))
    if department:
        q = q.filter(Clinician.department == department)
    if location:
        q = q.filter(Clinician.location == location)
    return [ClinicianOut(id=c.id, full_name=c.full_name, department=c.department, specialty=c.specialty,
                         location=c.location, is_active=c.is_active) for c in q.order_by(Clinician.full_name)]


@staff_router.post("/slots", response_model=List[SlotOut], status_code=201)
def create_slots(payload: SlotIn, user: User = Depends(require_permission("appointment:manage")),
                 db: Session = Depends(get_db)):
    clinician = db.query(Clinician).filter(Clinician.id == payload.clinician_id, Clinician.is_active.is_(True)).first()
    if not clinician:
        raise HTTPException(status_code=404, detail="Clinician not found")
    start = to_utc_naive(payload.start)
    if start <= utcnow().replace(tzinfo=None):
        raise HTTPException(status_code=400, detail="Slots must start in the future")
    length = timedelta(minutes=payload.duration_minutes)
    created = []
    for i in range(payload.count):
        s, e = start + i * length, start + (i + 1) * length
        overlap = db.query(AppointmentSlot).filter(
            AppointmentSlot.clinician_id == clinician.id, AppointmentSlot.start_utc < e, AppointmentSlot.end_utc > s).first()
        if overlap:
            db.rollback()
            raise HTTPException(status_code=409, detail="A slot overlapping this time already exists for the clinician")
        slot = AppointmentSlot(clinician_id=clinician.id, start_utc=s, end_utc=e, created_by_user_id=user.id)
        db.add(slot)
        created.append(slot)
    db.flush()
    record_audit(db, user=user, action="slots_created", resource_type="clinician", resource_id=clinician.id,
                 detail={"count": len(created)})
    db.commit()
    return [_slot_out(s) for s in created]


@staff_router.get("/slots", response_model=List[SlotOut])
def staff_slots(department: Optional[str] = None, clinician_id: Optional[int] = None, location: Optional[str] = None,
                date_from: Optional[date] = None, date_to: Optional[date] = None, available_only: bool = True,
                user: User = Depends(require_permission("appointment:read_all")), db: Session = Depends(get_db)):
    rows = _query_slots(db, department=department, clinician_id=clinician_id, location=location,
                        date_from=date_from, date_to=date_to, available_only=available_only).limit(500).all()
    return [_slot_out(s) for s in rows]


@staff_router.post("/appointments", response_model=AppointmentOut, status_code=201)
def staff_book(payload: StaffBookRequest, user: User = Depends(require_permission("appointment:manage")),
               db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == payload.patient_id, Patient.status == "active").first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    appt = book_slot(db, patient_id=patient.id, slot_id=payload.slot_id, reason=payload.reason,
                     idempotency_key=payload.idempotency_key, source="staff", actor=user)
    return _appt_out(appt)


@staff_router.get("/appointments")
def staff_list_appointments(
    status: Optional[str] = None, department: Optional[str] = None, patient_id: Optional[int] = None,
    change_requested: Optional[bool] = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_permission("appointment:read_all")), db: Session = Depends(get_db),
):
    q = db.query(Appointment)
    if status:
        q = q.filter(Appointment.status == status)
    if department:
        q = q.filter(Appointment.department == department)
    if patient_id:
        q = q.filter(Appointment.patient_id == patient_id)
    if change_requested:
        q = q.filter(Appointment.change_request.isnot(None))
    total = q.count()
    rows = q.order_by(Appointment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_appt_out(a) for a in rows], "total": total, "page": page, "page_size": page_size}


@staff_router.get("/overview")
def appointment_overview(user: User = Depends(require_permission("appointment:read_all")), db: Session = Depends(get_db)):
    by_status = dict(db.query(Appointment.status, func.count(Appointment.id)).group_by(Appointment.status).all())
    now = utcnow().replace(tzinfo=None)
    upcoming = (db.query(func.count(Appointment.id)).join(AppointmentSlot, Appointment.slot_id == AppointmentSlot.id)
                .filter(Appointment.status.in_(("pending", "confirmed")), AppointmentSlot.start_utc > now).scalar())
    open_slots = db.query(func.count(AppointmentSlot.id)).filter(
        AppointmentSlot.status == "open", AppointmentSlot.start_utc > now).scalar()
    pending_changes = db.query(func.count(Appointment.id)).filter(Appointment.change_request.isnot(None)).scalar()
    return {"by_status": by_status, "upcoming": upcoming, "open_slots": open_slots,
            "pending_change_requests": pending_changes}


def _get_appt(db: Session, appt_id: int) -> Appointment:
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt


@staff_router.post("/appointments/{appt_id}/confirm", response_model=AppointmentOut)
def confirm_appointment(appt_id: int, user: User = Depends(require_permission("appointment:manage")),
                        db: Session = Depends(get_db)):
    appt = _get_appt(db, appt_id)
    if appt.status not in ("requested", "pending") or appt.slot_id is None:
        raise HTTPException(status_code=409, detail="Only a pending appointment holding a slot can be confirmed")
    appt.status = "confirmed"
    _queue_notifications(db, appt, appt.slot, "booking_confirmation")
    record_audit(db, user=user, action="appointment_confirmed", resource_type="appointment", resource_id=appt.id,
                 patient_id=appt.patient_id)
    db.commit()
    return _appt_out(appt)


@staff_router.post("/appointments/{appt_id}/cancel", response_model=AppointmentOut)
def staff_cancel(appt_id: int, user: User = Depends(require_permission("appointment:manage")),
                 db: Session = Depends(get_db)):
    appt = _get_appt(db, appt_id)
    _cancel(db, appt, user, "Cancelled by staff")
    db.commit()
    return _appt_out(appt)


@staff_router.post("/appointments/{appt_id}/complete", response_model=AppointmentOut)
def complete_appointment(appt_id: int, user: User = Depends(require_permission("appointment:manage")),
                         db: Session = Depends(get_db)):
    appt = _get_appt(db, appt_id)
    if appt.status != "confirmed":
        raise HTTPException(status_code=409, detail="Only a confirmed appointment can be completed")
    appt.status = "completed"
    record_audit(db, user=user, action="appointment_completed", resource_type="appointment", resource_id=appt.id,
                 patient_id=appt.patient_id)
    db.commit()
    return _appt_out(appt)


@staff_router.post("/appointments/{appt_id}/resolve-change", response_model=AppointmentOut)
def resolve_change(appt_id: int, payload: ResolveChangeIn, user: User = Depends(require_permission("appointment:manage")),
                   db: Session = Depends(get_db)):
    appt = _get_appt(db, appt_id)
    if not appt.change_request:
        raise HTTPException(status_code=409, detail="No change request is pending on this appointment")
    if payload.action == "reject":
        appt.change_request = None
        appt.change_request_note = None
    elif appt.change_request == "cancel":
        _cancel(db, appt, user, "Cancelled at patient request")
    else:  # reschedule: win the new slot first, then release the old one
        if not payload.new_slot_id:
            raise HTTPException(status_code=400, detail="new_slot_id is required to approve a reschedule")
        new_slot = db.query(AppointmentSlot).filter(AppointmentSlot.id == payload.new_slot_id).first()
        if not new_slot or new_slot.start_utc <= utcnow().replace(tzinfo=None):
            raise HTTPException(status_code=404, detail="New slot not found or already in the past")
        won = db.execute(update(AppointmentSlot).where(AppointmentSlot.id == new_slot.id, AppointmentSlot.status == "open")
                         .values(status="booked")).rowcount
        if won != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="The new slot is no longer available")
        old_slot_id = appt.slot_id
        appt.slot_id = new_slot.id
        appt.department = new_slot.clinician.department
        appt.change_request = None
        appt.change_request_note = None
        release_slot(db, old_slot_id)
        db.flush()
        _queue_notifications(db, appt, new_slot, "booking_confirmation")
    record_audit(db, user=user, action="appointment_change_resolved", resource_type="appointment",
                 resource_id=appt.id, patient_id=appt.patient_id, detail={"action": payload.action})
    db.commit()
    return _appt_out(appt)


@staff_router.post("/follow-ups", status_code=201)
def create_follow_up(payload: FollowUpIn, user: User = Depends(require_permission("task:write", "patient:read")),
                     db: Session = Depends(get_db)):
    """Create a follow-up instruction. It stays invisible to the patient until a clinician approves it."""
    if not db.query(Patient).filter(Patient.id == payload.patient_id).first():
        raise HTTPException(status_code=404, detail="Patient not found")
    fu = FollowUpInstruction(patient_id=payload.patient_id, instruction=payload.instruction,
                             appointment_id=payload.appointment_id, due_date=payload.due_date,
                             created_by_user_id=user.id)
    db.add(fu)
    db.flush()
    record_audit(db, user=user, action="followup_created", resource_type="follow_up", resource_id=fu.id,
                 patient_id=payload.patient_id)
    db.commit()
    return {"id": fu.id, "visible_to_patient": False}


@staff_router.post("/follow-ups/{fu_id}/approve")
def approve_follow_up(fu_id: int, user: User = Depends(require_permission("followup:approve")),
                      db: Session = Depends(get_db)):
    fu = db.query(FollowUpInstruction).filter(FollowUpInstruction.id == fu_id).first()
    if not fu:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    fu.approved_by_user_id = user.id
    fu.approved_at = utcnow()
    fu.visible_to_patient = True
    record_audit(db, user=user, action="followup_approved", resource_type="follow_up", resource_id=fu.id,
                 patient_id=fu.patient_id)
    db.commit()
    return {"id": fu.id, "visible_to_patient": True}


# ---------------------------------------------------------------------------
# Patient portal API (every query is scoped to the caller's own patient_id)
# ---------------------------------------------------------------------------
@portal_router.get("/me")
def portal_me(user: User = Depends(require_patient_portal), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == user.patient_id).first()
    return {"full_name": patient.full_name, "preferred_language": patient.preferred_language,
            "contact_preference": patient.contact_preference, "timezone": get_settings().hospital_timezone}


@portal_router.get("/directory")
def portal_directory(user: User = Depends(require_patient_portal), db: Session = Depends(get_db)):
    """Departments, clinicians and locations that currently have bookable slots."""
    rows = (db.query(Clinician).join(AppointmentSlot).filter(
        Clinician.is_active.is_(True), AppointmentSlot.status == "open",
        AppointmentSlot.start_utc > utcnow().replace(tzinfo=None)).distinct().all())
    return {
        "departments": sorted({c.department for c in rows}),
        "locations": sorted({c.location for c in rows}),
        "clinicians": [{"id": c.id, "name": c.full_name, "department": c.department, "location": c.location}
                       for c in sorted(rows, key=lambda c: c.full_name)],
    }


@portal_router.get("/slots", response_model=List[SlotOut])
def portal_slots(department: Optional[str] = None, clinician_id: Optional[int] = None, location: Optional[str] = None,
                 date_from: Optional[date] = None, date_to: Optional[date] = None,
                 user: User = Depends(require_patient_portal), db: Session = Depends(get_db)):
    rows = _query_slots(db, department=department, clinician_id=clinician_id, location=location,
                        date_from=date_from, date_to=date_to).limit(200).all()
    return [_slot_out(s) for s in rows]


@portal_router.post("/appointments", response_model=AppointmentOut, status_code=201)
def portal_book(payload: BookRequest, user: User = Depends(require_patient_portal), db: Session = Depends(get_db)):
    appt = book_slot(db, patient_id=user.patient_id, slot_id=payload.slot_id, reason=payload.reason,
                     idempotency_key=payload.idempotency_key, source="portal", actor=user)
    return _appt_out(appt)


@portal_router.get("/appointments", response_model=List[AppointmentOut])
def portal_appointments(scope: str = Query("upcoming", pattern="^(upcoming|past|all)$"),
                        user: User = Depends(require_patient_portal), db: Session = Depends(get_db)):
    now = utcnow().replace(tzinfo=None)
    rows = db.query(Appointment).outerjoin(AppointmentSlot, Appointment.slot_id == AppointmentSlot.id).filter(
        Appointment.patient_id == user.patient_id)
    if scope == "upcoming":
        rows = rows.filter(Appointment.status.in_(("requested", "pending", "confirmed")), AppointmentSlot.start_utc > now)
    elif scope == "past":
        rows = rows.filter((AppointmentSlot.start_utc <= now) | (Appointment.status.in_(("cancelled", "completed"))))
    return [_appt_out(a) for a in rows.order_by(AppointmentSlot.start_utc.desc()).limit(100).all()]


@portal_router.post("/appointments/{appt_id}/request-change", response_model=AppointmentOut)
def portal_request_change(appt_id: int, payload: ChangeRequestIn, user: User = Depends(require_patient_portal),
                          db: Session = Depends(get_db)):
    appt = db.query(Appointment).filter(Appointment.id == appt_id, Appointment.patient_id == user.patient_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")  # same answer for other patients' ids
    if appt.status not in ("pending", "confirmed"):
        raise HTTPException(status_code=409, detail="Only pending or confirmed appointments can be changed")
    if appt.change_request:
        raise HTTPException(status_code=409, detail="A change request is already awaiting staff review")
    appt.change_request = payload.request_type
    appt.change_request_note = payload.note
    patient = db.get(Patient, user.patient_id)
    create_ticket(db, {
        "category": "Appointment rescheduling and cancellation", "intent": "portal_change_request",
        "title": f"Patient requests to {payload.request_type} appointment #{appt.id}",
        "description": f"Appointment #{appt.id} ({appt.department}): patient asked to {payload.request_type}.",
        "raw_quote": (payload.note or "")[:300], "translated_quote": (payload.note or "")[:300], "language": "en",
        "urgency": "ROUTINE", "priority_rationale": "Portal change request; staff must act before the slot changes.",
        "required_action": "Review the request and approve or reject it in the scheduling view.",
        "patient_name": patient.full_name,
    }, call_id=None, patient_id=patient.id, actor="Patient Portal", source_note="Created from portal change request",
        dedupe=False)
    record_audit(db, user=user, action="appointment_change_requested", resource_type="appointment",
                 resource_id=appt.id, patient_id=appt.patient_id, detail={"type": payload.request_type})
    db.commit()
    return _appt_out(appt)


@portal_router.get("/notifications")
def portal_notifications(user: User = Depends(require_patient_portal), db: Session = Depends(get_db)):
    rows = (db.query(Notification).filter(Notification.patient_id == user.patient_id, Notification.channel == "in_app",
                                          Notification.scheduled_for <= utcnow().replace(tzinfo=None))
            .order_by(Notification.scheduled_for.desc()).limit(50).all())
    return [{"id": n.id, "kind": n.kind, "body": n.body, "at": as_utc(n.scheduled_for)} for n in rows]


@portal_router.get("/follow-ups")
def portal_follow_ups(user: User = Depends(require_patient_portal), db: Session = Depends(get_db)):
    rows = (db.query(FollowUpInstruction).filter(FollowUpInstruction.patient_id == user.patient_id,
                                                 FollowUpInstruction.visible_to_patient.is_(True))
            .order_by(FollowUpInstruction.approved_at.desc()).all())
    return [{"id": f.id, "instruction": f.instruction, "due_date": f.due_date, "approved_at": f.approved_at} for f in rows]


_REQUEST_CATEGORY = {
    "general": "General inquiries and information requests", "billing": "Billing and payment queries",
    "insurance": "Insurance and pre-authorisation queries", "prescription": "Medication, pharmacy and prescription queries",
    "report_followup": "Promised callbacks and other follow-up commitments", "complaint": "General inquiries and information requests",
}
_PATIENT_STATUS = {
    "PENDING": "Received", "AWAITING_REVIEW": "Received", "ASSIGNED": "With our team", "IN_PROGRESS": "With our team",
    "DISPATCHED": "With our team", "AWAITING_PATIENT": "We need information from you",
    "AWAITING_EXTERNAL": "With our team", "RESOLVED": "Completed", "CLOSED": "Completed",
}


@portal_router.post("/requests", status_code=201)
def portal_create_request(payload: PatientRequestIn, user: User = Depends(require_patient_portal),
                          db: Session = Depends(get_db)):
    if payload.idempotency_key:
        prior = db.query(PatientRequest).filter(PatientRequest.patient_id == user.patient_id,
                                                PatientRequest.idempotency_key == payload.idempotency_key).first()
        if prior:
            return {"id": prior.id, "status": "Received"}
    patient = db.get(Patient, user.patient_id)
    title = f"Patient portal request: {payload.request_type.replace('_', ' ')}"
    ticket = create_ticket(db, {
        "category": _REQUEST_CATEGORY[payload.request_type], "intent": "portal_request",
        "title": title, "description": payload.message, "raw_quote": payload.message[:300],
        "translated_quote": payload.message[:300], "language": "en", "urgency": "INQUIRY",
        "priority_rationale": "Routine portal request. Not for emergencies - patients are told to call emergency services.",
        "required_action": "Respond to the patient through the preferred contact channel.",
        "patient_name": patient.full_name,
    }, call_id=None, patient_id=patient.id, actor="Patient Portal", source_note="Created from patient portal", dedupe=False)
    req = PatientRequest(patient_id=patient.id, request_type=payload.request_type, message=payload.message,
                         ticket_id=ticket.id if ticket else None, idempotency_key=payload.idempotency_key)
    db.add(req)
    db.flush()
    record_audit(db, user=user, action="patient_request_created", resource_type="patient_request",
                 resource_id=req.id, patient_id=patient.id, detail={"type": payload.request_type})
    db.commit()
    return {"id": req.id, "status": "Received"}


@portal_router.get("/requests")
def portal_requests(user: User = Depends(require_patient_portal), db: Session = Depends(get_db)):
    rows = (db.query(PatientRequest).filter(PatientRequest.patient_id == user.patient_id)
            .order_by(PatientRequest.created_at.desc()).limit(50).all())
    out = []
    for r in rows:
        ticket = db.get(Ticket, r.ticket_id) if r.ticket_id else None
        out.append({"id": r.id, "request_type": r.request_type, "message": r.message, "created_at": r.created_at,
                    "status": _PATIENT_STATUS.get(ticket.status, "Received") if ticket else "Received"})
    return out
