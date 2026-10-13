"""Domain models added for patient coordination.

Kept separate from ``database.py`` (which owns Call/Ticket/AuditLog) so each concept
stays distinct:

1. Patient profile            -> ``Patient``
2. Conversation / transcript  -> ``Call`` (database.py)
3. Clinical record            -> ``PatientClinicalRecord``
4. Medication / prescription  -> ``Medication``
5. Task and assignment        -> ``Ticket`` (database.py)
6. Appointment                -> ``AppointmentSlot`` / ``Appointment``
7. Audit event                -> ``AuditEvent`` (hash-chained, separate from per-ticket ``AuditLog``)
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Date, ForeignKey, Boolean,
    CheckConstraint, UniqueConstraint, Index, text,
)
from sqlalchemy.orm import relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uid() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
USER_ROLES = ("admin", "nurse", "clinician", "coordinator", "pharmacist", "patient")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(String(20), nullable=False, index=True)
    # Staff scoping: coordinators/pharmacists only see tasks routed to this team.
    department = Column(String(100), nullable=True)
    # Patient portal accounts are bound to exactly one patient profile.
    patient_id = Column(Integer, ForeignKey("patients.id", use_alter=True, name="fk_users_patient"), nullable=True, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    failed_logins = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    token_version = Column(Integer, nullable=False, default=0)  # bump to revoke issued tokens
    created_at = Column(DateTime, nullable=False, default=utcnow)
    last_login_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','nurse','clinician','coordinator','pharmacist','patient')",
            name="ck_users_role",
        ),
    )


# ---------------------------------------------------------------------------
# Patient profile
# ---------------------------------------------------------------------------
class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    # Opaque internal identifier safe to use in URLs/logs (never the name or MRN).
    patient_uid = Column(String(32), nullable=False, unique=True, default=new_uid, index=True)
    # Identifier issued by the hospital's own records system, when integrated.
    mrn = Column(String(50), nullable=True, unique=True, index=True)
    full_name = Column(String(150), nullable=False)
    name_key = Column(String(150), nullable=False, index=True)      # normalised for matching
    phonetic_key = Column(String(60), nullable=False, default="", index=True)
    date_of_birth = Column(Date, nullable=True)
    sex = Column(String(20), nullable=True)
    phone = Column(String(50), nullable=True, index=True)
    email = Column(String(150), nullable=True)
    preferred_language = Column(String(20), nullable=True)
    contact_preference = Column(String(20), nullable=False, default="in_app")  # in_app|sms|email|phone
    # Identity must be confirmed by staff before clinical data is attached.
    identity_verified = Column(Boolean, nullable=False, default=False)
    verified_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active|merged|inactive
    merged_into_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    clinical_records = relationship("PatientClinicalRecord", back_populates="patient")
    medications = relationship("Medication", back_populates="patient")

    __table_args__ = (
        CheckConstraint("status IN ('active','merged','inactive')", name="ck_patients_status"),
        CheckConstraint(
            "contact_preference IN ('in_app','sms','email','phone')", name="ck_patients_contact_pref"
        ),
    )


class PatientClinicalRecord(Base):
    """Allergies, conditions and history. Clinician-entered or imported from a hospital record."""
    __tablename__ = "patient_clinical_records"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    record_type = Column(String(20), nullable=False)  # allergy|condition|history|note
    description = Column(Text, nullable=False)
    severity = Column(String(30), nullable=True)
    source = Column(String(30), nullable=False)       # clinician_entered|hospital_record
    source_ref = Column(String(100), nullable=True)   # id in the external system, if any
    recorded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=utcnow)
    entered_in_error = Column(Boolean, nullable=False, default=False)

    patient = relationship("Patient", back_populates="clinical_records")

    __table_args__ = (
        CheckConstraint(
            "record_type IN ('allergy','condition','history','note')", name="ck_clinical_record_type"
        ),
        CheckConstraint(
            "source IN ('clinician_entered','hospital_record')", name="ck_clinical_record_source"
        ),
    )


class Medication(Base):
    """A *verified* prescription. Never created or edited from transcripts or AI output.

    Rows are immutable once written; a change is a new row that ``supersedes`` the old one,
    so the full prescription history stays reconstructable.
    """
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    medicine = Column(String(150), nullable=False)
    dose = Column(String(60), nullable=False)
    route = Column(String(40), nullable=False)
    frequency = Column(String(80), nullable=False)
    duration = Column(String(80), nullable=True)
    prescriber_name = Column(String(120), nullable=False)
    prescriber_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    prescription_ref = Column(String(100), nullable=True)  # reference in the pharmacy/EHR system
    source = Column(String(30), nullable=False)             # clinician_entered|hospital_pharmacy
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active|stopped|superseded|entered_in_error
    supersedes_id = Column(Integer, ForeignKey("medications.id"), nullable=True)
    verified_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    verified_at = Column(DateTime, nullable=False, default=utcnow)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    patient = relationship("Patient", back_populates="medications")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','stopped','superseded','entered_in_error')", name="ck_medication_status"
        ),
        CheckConstraint(
            "source IN ('clinician_entered','hospital_pharmacy')", name="ck_medication_source"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="ck_medication_dates"
        ),
        # A medication can be superseded by at most one newer row.
        Index("uq_medication_supersedes", "supersedes_id", unique=True),
    )


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------
class Clinician(Base):
    __tablename__ = "clinicians"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    department = Column(String(100), nullable=False, index=True)
    specialty = Column(String(100), nullable=True)
    location = Column(String(120), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


class AppointmentSlot(Base):
    """A bookable time. Slots are only ever created by staff/integration - never invented."""
    __tablename__ = "appointment_slots"

    id = Column(Integer, primary_key=True)
    clinician_id = Column(Integer, ForeignKey("clinicians.id"), nullable=False, index=True)
    start_utc = Column(DateTime, nullable=False, index=True)
    end_utc = Column(DateTime, nullable=False)
    status = Column(String(10), nullable=False, default="open", index=True)  # open|booked|blocked
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    clinician = relationship("Clinician")

    __table_args__ = (
        UniqueConstraint("clinician_id", "start_utc", name="uq_slot_clinician_start"),
        CheckConstraint("end_utc > start_utc", name="ck_slot_range"),
        CheckConstraint("status IN ('open','booked','blocked')", name="ck_slot_status"),
    )


ACTIVE_APPOINTMENT_STATUSES = ("requested", "pending", "confirmed")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    slot_id = Column(Integer, ForeignKey("appointment_slots.id"), nullable=True)
    department = Column(String(100), nullable=False)
    reason = Column(String(300), nullable=True)
    status = Column(String(12), nullable=False, default="requested", index=True)
    source = Column(String(20), nullable=False, default="portal")  # portal|staff|conversation
    conversation_id = Column(Integer, ForeignKey("calls.id"), nullable=True)
    idempotency_key = Column(String(100), nullable=True)
    change_request = Column(String(12), nullable=True)  # reschedule|cancel (awaiting staff action)
    change_request_note = Column(String(300), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_reason = Column(String(300), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    slot = relationship("AppointmentSlot")
    patient = relationship("Patient")

    __table_args__ = (
        CheckConstraint(
            "status IN ('requested','pending','confirmed','cancelled','completed')",
            name="ck_appointment_status",
        ),
        CheckConstraint(
            "change_request IS NULL OR change_request IN ('reschedule','cancel')",
            name="ck_appointment_change_request",
        ),
        UniqueConstraint("patient_id", "idempotency_key", name="uq_appointment_patient_idem"),
        # Database-level double-booking guard: one live appointment per slot.
        Index(
            "uq_appointment_active_slot", "slot_id", unique=True,
            sqlite_where=text("status IN ('requested','pending','confirmed')"),
            postgresql_where=text("status IN ('requested','pending','confirmed')"),
        ),
    )


class FollowUpInstruction(Base):
    """Instructions shown to a patient only after a clinician/coordinator approves them."""
    __tablename__ = "follow_up_instructions"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    instruction = Column(Text, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    visible_to_patient = Column(Boolean, nullable=False, default=False)
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class PatientRequest(Base):
    """Routine request submitted from the portal. Creates a staff task; status mirrors the task."""
    __tablename__ = "patient_requests"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    request_type = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    idempotency_key = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("patient_id", "idempotency_key", name="uq_patient_request_idem"),
    )


class Notification(Base):
    """Outbox. Rows are delivered by a channel provider; without one configured they stay
    ``pending`` (``in_app`` is delivered by being readable through the API)."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    channel = Column(String(10), nullable=False)       # in_app|sms|email
    kind = Column(String(30), nullable=False)          # booking_confirmation|reminder|cancellation|followup
    body = Column(Text, nullable=False)                # minimal, PHI-light text
    scheduled_for = Column(DateTime, nullable=False, default=utcnow, index=True)
    status = Column(String(12), nullable=False, default="pending", index=True)  # pending|sent|failed|unavailable
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    sent_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Routing configuration
# ---------------------------------------------------------------------------
class RoutingRule(Base):
    __tablename__ = "routing_rules"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    priority = Column(Integer, nullable=False, default=100, index=True)  # lower runs first
    match_category = Column(String(60), nullable=True)   # task category, null = any
    match_urgency = Column(String(20), nullable=True)
    match_keyword = Column(String(80), nullable=True)    # case-insensitive substring of task text
    target_team = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class AppSetting(Base):
    """Small admin-editable key/value store (fallback queue, SLA minutes, escalation policy)."""
    __tablename__ = "app_settings"

    key = Column(String(80), primary_key=True)
    value = Column(Text, nullable=False)  # JSON
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------------------
# Speech-to-text jobs
# ---------------------------------------------------------------------------
class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    id = Column(String(32), primary_key=True, default=new_uid)
    status = Column(String(12), nullable=False, default="queued", index=True)  # queued|running|succeeded|failed
    requested_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    language_requested = Column(String(20), nullable=True)
    provider_used = Column(String(40), nullable=True)
    audio_path = Column(String(255), nullable=True)   # file name inside the private audio dir
    consent_confirmed = Column(Boolean, nullable=False, default=False)
    retain_audio = Column(Boolean, nullable=False, default=False)
    result_json = Column(Text, nullable=True)
    error_code = Column(String(40), nullable=True)
    error_message = Column(String(300), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    audio_delete_after = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class AuditEvent(Base):
    """Append-only, hash-chained record of sensitive reads and writes.

    ``detail`` holds identifiers and changed field *names*, never clinical free text.
    """
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True)
    occurred_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_role = Column(String(20), nullable=True)
    action = Column(String(60), nullable=False, index=True)
    resource_type = Column(String(40), nullable=False)
    resource_id = Column(String(40), nullable=True)
    patient_id = Column(Integer, nullable=True, index=True)
    outcome = Column(String(10), nullable=False, default="success")  # success|denied|error
    detail = Column(Text, nullable=False, default="{}")
    prev_hash = Column(String(64), nullable=False, default="")
    event_hash = Column(String(64), nullable=False, default="")
