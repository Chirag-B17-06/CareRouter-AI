"""Patient profiles, clinical records and verified medications.

Concept separation (see models_care.py):
  * ``Patient``                 - who the person is (demographics, contact, identity status)
  * ``PatientClinicalRecord``   - clinician-entered / hospital-sourced history, allergies
  * ``Medication``              - verified prescriptions only; immutable rows, changes supersede
Nothing in this module is reachable from transcript or AI output: prescriptions and clinical
facts are only created by an authenticated clinician/pharmacist who attests to them.
"""
import json
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from audit import record_audit
from auth import assert_patient_access, require_permission
from database import Call, Ticket, get_db
from models_care import (
    Appointment, Medication, Patient, PatientClinicalRecord, User, utcnow,
)
from patient_matching import MatchCandidate, find_candidates, likely_duplicates, normalize_name, phonetic_key

router = APIRouter(prefix="/api/patients", tags=["patients"])

CONTACT_PREFERENCES = ("in_app", "sms", "email", "phone")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class PatientCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    mrn: Optional[str] = Field(None, max_length=50)
    date_of_birth: Optional[date] = None
    sex: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    preferred_language: Optional[str] = Field(None, max_length=20)
    contact_preference: str = "in_app"
    # Must be true to create a profile even though similar patients already exist.
    confirm_not_duplicate: bool = False

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v):
        if v and (v > date.today() or v.year < 1900):
            raise ValueError("date_of_birth is not plausible")
        return v

    @field_validator("contact_preference")
    @classmethod
    def _pref(cls, v):
        if v not in CONTACT_PREFERENCES:
            raise ValueError(f"contact_preference must be one of {CONTACT_PREFERENCES}")
        return v


class PatientUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    date_of_birth: Optional[date] = None
    sex: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    preferred_language: Optional[str] = Field(None, max_length=20)
    contact_preference: Optional[str] = None

    @field_validator("contact_preference")
    @classmethod
    def _pref(cls, v):
        if v is not None and v not in CONTACT_PREFERENCES:
            raise ValueError(f"contact_preference must be one of {CONTACT_PREFERENCES}")
        return v


class PatientOut(BaseModel):
    id: int
    patient_uid: str
    mrn: Optional[str]
    full_name: str
    date_of_birth: Optional[date]
    sex: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    preferred_language: Optional[str]
    contact_preference: str
    identity_verified: bool
    status: str
    created_at: datetime


class PatientSummary(BaseModel):
    id: int
    patient_uid: str
    full_name: str
    mrn: Optional[str]
    date_of_birth: Optional[date]
    identity_verified: bool


class PatientPage(BaseModel):
    items: List[PatientSummary]
    total: int
    page: int
    page_size: int


class MatchRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    date_of_birth: Optional[date] = None
    age: Optional[int] = Field(None, ge=0, le=130)
    phone: Optional[str] = Field(None, max_length=50)
    mrn: Optional[str] = Field(None, max_length=50)


class CandidateOut(BaseModel):
    patient_id: int
    patient_uid: str
    display_name: str
    score: float
    confidence_band: str
    signals: List[str]
    identity_verified: bool


class ClinicalRecordIn(BaseModel):
    record_type: str
    description: str = Field(..., min_length=2, max_length=2000)
    severity: Optional[str] = Field(None, max_length=30)
    source: str = "clinician_entered"
    source_ref: Optional[str] = Field(None, max_length=100)

    @field_validator("record_type")
    @classmethod
    def _type(cls, v):
        if v not in ("allergy", "condition", "history", "note"):
            raise ValueError("record_type must be allergy, condition, history or note")
        return v

    @field_validator("source")
    @classmethod
    def _source(cls, v):
        if v not in ("clinician_entered", "hospital_record"):
            raise ValueError("source must be clinician_entered or hospital_record")
        return v


class ClinicalRecordOut(BaseModel):
    id: int
    record_type: str
    description: str
    severity: Optional[str]
    source: str
    source_ref: Optional[str]
    recorded_by_user_id: int
    recorded_at: datetime
    entered_in_error: bool


class MedicationIn(BaseModel):
    medicine: str = Field(..., min_length=2, max_length=150)
    dose: str = Field(..., min_length=1, max_length=60)
    route: str = Field(..., min_length=1, max_length=40)
    frequency: str = Field(..., min_length=1, max_length=80)
    duration: Optional[str] = Field(None, max_length=80)
    prescriber_name: str = Field(..., min_length=2, max_length=120)
    prescription_ref: Optional[str] = Field(None, max_length=100)
    source: str = "clinician_entered"
    effective_from: date
    effective_to: Optional[date] = None
    # Explicit attestation by the authenticated clinician/pharmacist that this matches the
    # authoritative prescription. Without it nothing is stored.
    attest_verified: bool = False

    @field_validator("source")
    @classmethod
    def _source(cls, v):
        if v not in ("clinician_entered", "hospital_pharmacy"):
            raise ValueError("source must be clinician_entered or hospital_pharmacy")
        return v


class MedicationOut(BaseModel):
    id: int
    patient_id: int
    medicine: str
    dose: str
    route: str
    frequency: str
    duration: Optional[str]
    prescriber_name: str
    prescription_ref: Optional[str]
    source: str
    effective_from: date
    effective_to: Optional[date]
    status: str
    supersedes_id: Optional[int]
    verified_by_user_id: int
    verified_at: datetime


class StopMedication(BaseModel):
    effective_to: date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_patient(db: Session, patient_id: int, user: User) -> Patient:
    assert_patient_access(user, patient_id)
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def patient_out(p: Patient) -> PatientOut:
    return PatientOut(
        id=p.id, patient_uid=p.patient_uid, mrn=p.mrn, full_name=p.full_name, date_of_birth=p.date_of_birth,
        sex=p.sex, phone=p.phone, email=p.email, preferred_language=p.preferred_language,
        contact_preference=p.contact_preference, identity_verified=p.identity_verified,
        status=p.status, created_at=p.created_at,
    )


def candidate_out(c: MatchCandidate) -> CandidateOut:
    return CandidateOut(
        patient_id=c.patient_id, patient_uid=c.patient_uid, display_name=c.display_name, score=c.score,
        confidence_band=c.confidence_band, signals=c.signals, identity_verified=c.identity_verified,
    )


def _med_out(m: Medication) -> MedicationOut:
    return MedicationOut(
        id=m.id, patient_id=m.patient_id, medicine=m.medicine, dose=m.dose, route=m.route,
        frequency=m.frequency, duration=m.duration, prescriber_name=m.prescriber_name,
        prescription_ref=m.prescription_ref, source=m.source, effective_from=m.effective_from,
        effective_to=m.effective_to, status=m.status, supersedes_id=m.supersedes_id,
        verified_by_user_id=m.verified_by_user_id, verified_at=m.verified_at,
    )


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
@router.get("", response_model=PatientPage)
def search_patients(
    q: Optional[str] = Query(None, max_length=100), page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("patient:read")), db: Session = Depends(get_db),
):
    query = db.query(Patient).filter(Patient.status == "active")
    if q and q.strip():
        term = q.strip()
        clauses = [Patient.name_key.like(f"%{normalize_name(term)}%"), Patient.mrn == term,
                   Patient.patient_uid == term.lower()]
        if len("".join(ch for ch in term if ch.isdigit())) >= 6:
            clauses.append(Patient.phone.like(f"%{''.join(ch for ch in term if ch.isdigit())[-8:]}"))
        clauses.append(Patient.phonetic_key == phonetic_key(term))
        query = query.filter(or_(*clauses))
    total = query.count()
    rows = query.order_by(Patient.full_name).offset((page - 1) * page_size).limit(page_size).all()
    # Free-text search terms are names/ids, so only their length is logged.
    record_audit(db, user=user, action="patient_search", resource_type="patient",
                 detail={"query_length": len(q or ""), "results": len(rows)}, commit=True)
    return PatientPage(
        items=[PatientSummary(id=p.id, patient_uid=p.patient_uid, full_name=p.full_name, mrn=p.mrn,
                              date_of_birth=p.date_of_birth, identity_verified=p.identity_verified) for p in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/match", response_model=List[CandidateOut])
def match_patient(payload: MatchRequest, user: User = Depends(require_permission("patient:read")),
                  db: Session = Depends(get_db)):
    if not any([payload.name, payload.mrn, payload.phone]):
        raise HTTPException(status_code=400, detail="Provide at least a name, MRN or phone number")
    cands = find_candidates(db, name=payload.name, dob=payload.date_of_birth, age=payload.age,
                            phone=payload.phone, mrn=payload.mrn)
    record_audit(db, user=user, action="patient_match_query", resource_type="patient",
                 detail={"results": len(cands)}, commit=True)
    return [candidate_out(c) for c in cands]


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(payload: PatientCreate, user: User = Depends(require_permission("patient:write")),
                   db: Session = Depends(get_db)):
    dupes = likely_duplicates(db, name=payload.full_name, dob=payload.date_of_birth, phone=payload.phone, mrn=payload.mrn)
    if dupes and not payload.confirm_not_duplicate:
        raise HTTPException(status_code=409, detail={
            "message": "Similar patient profiles already exist. Review them, or resubmit with "
                       "confirm_not_duplicate=true if this is a different person.",
            "candidates": [candidate_out(c).model_dump() for c in dupes],
        })
    patient = Patient(
        full_name=payload.full_name.strip(), name_key=normalize_name(payload.full_name),
        phonetic_key=phonetic_key(payload.full_name), mrn=(payload.mrn or None), date_of_birth=payload.date_of_birth,
        sex=payload.sex, phone=payload.phone, email=payload.email, preferred_language=payload.preferred_language,
        contact_preference=payload.contact_preference, created_by_user_id=user.id,
    )
    db.add(patient)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A patient with this MRN already exists")
    record_audit(db, user=user, action="patient_created", resource_type="patient", resource_id=patient.id,
                 patient_id=patient.id, detail={"override_duplicate_warning": bool(dupes)})
    db.commit()
    return patient_out(patient)


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, user: User = Depends(require_permission("patient:read")), db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    record_audit(db, user=user, action="patient_viewed", resource_type="patient", resource_id=patient.id,
                 patient_id=patient.id, commit=True)
    return patient_out(patient)


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: int, payload: PatientUpdate,
                   user: User = Depends(require_permission("patient:write")), db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(patient, key, value)
    if "full_name" in changes:
        patient.name_key = normalize_name(patient.full_name)
        patient.phonetic_key = phonetic_key(patient.full_name)
        patient.identity_verified = False   # an edited identity must be re-verified
        patient.verified_at = None
        patient.verified_by_user_id = None
    record_audit(db, user=user, action="patient_updated", resource_type="patient", resource_id=patient.id,
                 patient_id=patient.id, detail={"changed_fields": sorted(changes)})
    db.commit()
    return patient_out(patient)


@router.post("/{patient_id}/verify", response_model=PatientOut)
def verify_identity(patient_id: int, user: User = Depends(require_permission("patient:verify")),
                    db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    patient.identity_verified = True
    patient.verified_by_user_id = user.id
    patient.verified_at = utcnow()
    record_audit(db, user=user, action="patient_identity_verified", resource_type="patient",
                 resource_id=patient.id, patient_id=patient.id, commit=True)
    return patient_out(patient)


@router.get("/{patient_id}/timeline")
def patient_timeline(patient_id: int, user: User = Depends(require_permission("patient:read", "conversation:read")),
                     db: Session = Depends(get_db)):
    """Conversations, tasks and appointments for one patient (summaries only - no transcripts)."""
    patient = _get_patient(db, patient_id, user)
    calls = db.query(Call).filter(Call.patient_id == patient.id).order_by(Call.created_at.desc()).limit(50).all()
    tickets = db.query(Ticket).filter(Ticket.patient_id == patient.id).order_by(Ticket.created_at.desc()).limit(100).all()
    appts = db.query(Appointment).filter(Appointment.patient_id == patient.id).order_by(Appointment.created_at.desc()).limit(50).all()
    record_audit(db, user=user, action="patient_timeline_viewed", resource_type="patient", resource_id=patient.id,
                 patient_id=patient.id, commit=True)
    return {
        "conversations": [{"id": c.id, "created_at": c.created_at, "summary": c.summary, "language": c.language} for c in calls],
        "tasks": [{"id": t.id, "title": t.title, "status": t.status, "urgency": t.urgency,
                   "assigned_team": t.assigned_team, "created_at": t.created_at} for t in tickets],
        "appointments": [{"id": a.id, "status": a.status, "department": a.department,
                          "slot_id": a.slot_id, "created_at": a.created_at} for a in appts],
    }


# ---------------------------------------------------------------------------
# Clinical records
# ---------------------------------------------------------------------------
@router.get("/{patient_id}/clinical", response_model=List[ClinicalRecordOut])
def list_clinical(patient_id: int, user: User = Depends(require_permission("clinical:read")),
                  db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    rows = (db.query(PatientClinicalRecord)
            .filter(PatientClinicalRecord.patient_id == patient.id)
            .order_by(PatientClinicalRecord.recorded_at.desc()).all())
    record_audit(db, user=user, action="clinical_record_viewed", resource_type="patient", resource_id=patient.id,
                 patient_id=patient.id, detail={"count": len(rows)}, commit=True)
    return [ClinicalRecordOut(**{c: getattr(r, c) for c in ClinicalRecordOut.model_fields}) for r in rows]


@router.post("/{patient_id}/clinical", response_model=ClinicalRecordOut, status_code=201)
def add_clinical(patient_id: int, payload: ClinicalRecordIn,
                 user: User = Depends(require_permission("clinical:write")), db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    rec = PatientClinicalRecord(patient_id=patient.id, recorded_by_user_id=user.id, **payload.model_dump())
    db.add(rec)
    db.flush()
    record_audit(db, user=user, action="clinical_record_added", resource_type="clinical_record",
                 resource_id=rec.id, patient_id=patient.id, detail={"record_type": rec.record_type})
    db.commit()
    return ClinicalRecordOut(**{c: getattr(rec, c) for c in ClinicalRecordOut.model_fields})


@router.post("/{patient_id}/clinical/{record_id}/entered-in-error", response_model=ClinicalRecordOut)
def mark_clinical_error(patient_id: int, record_id: int, user: User = Depends(require_permission("clinical:write")),
                        db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    rec = db.query(PatientClinicalRecord).filter(PatientClinicalRecord.id == record_id,
                                                 PatientClinicalRecord.patient_id == patient.id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Clinical record not found")
    rec.entered_in_error = True       # records are never deleted - they are marked
    record_audit(db, user=user, action="clinical_record_marked_error", resource_type="clinical_record",
                 resource_id=rec.id, patient_id=patient.id)
    db.commit()
    return ClinicalRecordOut(**{c: getattr(rec, c) for c in ClinicalRecordOut.model_fields})


# ---------------------------------------------------------------------------
# Medications (verified prescriptions only)
# ---------------------------------------------------------------------------
@router.get("/{patient_id}/medications", response_model=List[MedicationOut])
def list_medications(patient_id: int, include_history: bool = False,
                     user: User = Depends(require_permission("medication:read")), db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    query = db.query(Medication).filter(Medication.patient_id == patient.id)
    if not include_history:
        query = query.filter(Medication.status == "active")
    rows = query.order_by(Medication.effective_from.desc(), Medication.id.desc()).all()
    record_audit(db, user=user, action="medications_viewed", resource_type="patient", resource_id=patient.id,
                 patient_id=patient.id, detail={"count": len(rows)}, commit=True)
    return [_med_out(m) for m in rows]


def _build_medication(patient: Patient, payload: MedicationIn, user: User,
                      supersedes_id: Optional[int] = None) -> Medication:
    if not payload.attest_verified:
        raise HTTPException(
            status_code=400,
            detail="Prescription details must be verified against the authoritative prescription "
                   "(set attest_verified=true). Prescriptions are never created from transcripts or by AI.",
        )
    if payload.effective_to and payload.effective_to < payload.effective_from:
        raise HTTPException(status_code=400, detail="effective_to cannot be before effective_from")
    data = payload.model_dump(exclude={"attest_verified"})
    return Medication(
        patient_id=patient.id, prescriber_user_id=user.id if user.role == "clinician" else None,
        verified_by_user_id=user.id, supersedes_id=supersedes_id, status="active", **data,
    )


@router.post("/{patient_id}/medications", response_model=MedicationOut, status_code=201)
def add_medication(patient_id: int, payload: MedicationIn,
                   user: User = Depends(require_permission("medication:write")), db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    # Re-prescribing the same drug must be an explicit supersede, never a silent second active row.
    clash = db.query(Medication).filter(
        Medication.patient_id == patient.id, Medication.status == "active",
        Medication.medicine.ilike(payload.medicine.strip()),
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail=(
            f"An active prescription for this medicine already exists (id {clash.id}). "
            "Use the supersede action to change it."))
    med = _build_medication(patient, payload, user)
    db.add(med)
    db.flush()
    record_audit(db, user=user, action="medication_added", resource_type="medication", resource_id=med.id,
                 patient_id=patient.id, detail={"source": med.source})
    db.commit()
    return _med_out(med)


@router.post("/{patient_id}/medications/{medication_id}/supersede", response_model=MedicationOut, status_code=201)
def supersede_medication(patient_id: int, medication_id: int, payload: MedicationIn,
                         user: User = Depends(require_permission("medication:write")), db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    old = db.query(Medication).filter(Medication.id == medication_id, Medication.patient_id == patient.id).first()
    if not old:
        raise HTTPException(status_code=404, detail="Medication not found")
    if old.status != "active":
        raise HTTPException(status_code=409, detail="Only an active prescription can be superseded")
    new = _build_medication(patient, payload, user, supersedes_id=old.id)
    try:
        old.status = "superseded"
        end = max(old.effective_from, payload.effective_from)
        if old.effective_to is None or old.effective_to > end:
            old.effective_to = end
        db.add(new)
        db.flush()
        record_audit(db, user=user, action="medication_superseded", resource_type="medication",
                     resource_id=new.id, patient_id=patient.id, detail={"supersedes": old.id})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This prescription was already superseded")
    return _med_out(new)


@router.post("/{patient_id}/medications/{medication_id}/stop", response_model=MedicationOut)
def stop_medication(patient_id: int, medication_id: int, payload: StopMedication,
                    user: User = Depends(require_permission("medication:write")), db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    med = db.query(Medication).filter(Medication.id == medication_id, Medication.patient_id == patient.id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    if med.status != "active":
        raise HTTPException(status_code=409, detail="Only an active prescription can be stopped")
    if payload.effective_to < med.effective_from:
        raise HTTPException(status_code=400, detail="effective_to cannot be before effective_from")
    med.status = "stopped"
    med.effective_to = payload.effective_to
    record_audit(db, user=user, action="medication_stopped", resource_type="medication", resource_id=med.id,
                 patient_id=patient.id)
    db.commit()
    return _med_out(med)


@router.post("/{patient_id}/medications/{medication_id}/entered-in-error", response_model=MedicationOut)
def medication_entered_in_error(patient_id: int, medication_id: int,
                                user: User = Depends(require_permission("medication:write")),
                                db: Session = Depends(get_db)):
    patient = _get_patient(db, patient_id, user)
    med = db.query(Medication).filter(Medication.id == medication_id, Medication.patient_id == patient.id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    med.status = "entered_in_error"
    record_audit(db, user=user, action="medication_entered_in_error", resource_type="medication",
                 resource_id=med.id, patient_id=patient.id)
    db.commit()
    return _med_out(med)


# ---------------------------------------------------------------------------
# Conversation <-> patient linking (human confirmation)
# ---------------------------------------------------------------------------
conversation_router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class LinkPatientRequest(BaseModel):
    patient_id: int


@conversation_router.post("/{call_id}/link-patient")
def link_patient(call_id: int, payload: LinkPatientRequest,
                 user: User = Depends(require_permission("patient:link")), db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    patient = db.query(Patient).filter(Patient.id == payload.patient_id, Patient.status == "active").first()
    if not call or not patient:
        raise HTTPException(status_code=404, detail="Conversation or patient not found")
    call.patient_id = patient.id
    call.patient_match_status = "confirmed"
    for ticket in call.tickets:
        ticket.patient_id = patient.id
    record_audit(db, user=user, action="conversation_patient_linked", resource_type="conversation",
                 resource_id=call.id, patient_id=patient.id, detail={"tasks_updated": len(call.tickets)})
    db.commit()
    return {"message": "Patient linked", "conversation_id": call.id, "patient_id": patient.id}


@conversation_router.post("/{call_id}/unlink-patient")
def unlink_patient(call_id: int, user: User = Depends(require_permission("patient:link")),
                   db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Conversation not found")
    previous = call.patient_id
    call.patient_id = None
    call.patient_match_status = "none"
    for ticket in call.tickets:
        ticket.patient_id = None
    record_audit(db, user=user, action="conversation_patient_unlinked", resource_type="conversation",
                 resource_id=call.id, patient_id=previous)
    db.commit()
    return {"message": "Patient link removed", "conversation_id": call.id}


@conversation_router.get("/{call_id}/patient-candidates", response_model=List[CandidateOut])
def conversation_candidates(call_id: int, user: User = Depends(require_permission("patient:read", "conversation:read")),
                            db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        stored = json.loads(call.patient_match_candidates or "[]")
    except ValueError:
        stored = []
    return [CandidateOut(**c) for c in stored]
