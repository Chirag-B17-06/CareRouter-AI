"""Strict schema for transcript -> structured information, plus grounding checks.

Every extractor (rule-based or LLM) must produce data that passes ``validate_extraction``.
That function is the single gate before anything is saved:

* unknown / extra fields are rejected (``extra="forbid"``),
* enumerations are closed,
* ``verified_diagnosis`` is always ``None`` - a transcript can only *mention* a diagnosis;
  verification belongs to the clinical record,
* values that claim to be quoted from the conversation (names, ages, ids, medicine names,
  evidence excerpts) must literally occur in the transcript, otherwise they are removed
  and the record is flagged for human review instead of silently trusting the extractor.
"""
import re
import unicodedata
from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaskCategory(str, Enum):
    appointment_scheduling = "appointment_scheduling"
    appointment_changes = "appointment_changes"
    billing_inquiry = "billing_inquiry"
    insurance_claims_inquiry = "insurance_claims_inquiry"
    prescription_clarification = "prescription_clarification"
    clinical_review = "clinical_review"
    discharge_coordination = "discharge_coordination"
    test_report_follow_up = "test_report_follow_up"
    complaint = "complaint"
    follow_up_commitment = "follow_up_commitment"
    general_patient_support = "general_patient_support"


class Priority(str, Enum):
    emergency = "emergency"
    urgent = "urgent"
    routine = "routine"
    inquiry = "inquiry"
    requires_review = "requires_review"


PRIORITY_RANK = {"emergency": 0, "urgent": 1, "requires_review": 2, "routine": 3, "inquiry": 4}


class Assertion(str, Enum):
    reported = "reported"      # stated as present
    negated = "negated"        # stated as absent / ruled out
    possible = "possible"      # hedged: "may have", "suspected", "possible"


class AppointmentIntentType(str, Enum):
    none = "none"
    book = "book"
    reschedule = "reschedule"
    cancel = "cancel"
    follow_up = "follow_up"


class PatientInfo(Strict):
    name: Optional[str] = Field(None, max_length=150)
    patient_id: Optional[str] = Field(None, max_length=50)
    age: Optional[int] = Field(None, ge=0, le=130)
    date_of_birth: Optional[date] = None
    caller_relationship: Optional[str] = Field(None, max_length=50)


class Symptom(Strict):
    text: str = Field(..., min_length=1, max_length=200)
    assertion: Assertion
    evidence: Optional[str] = Field(None, max_length=500)


class DiagnosisMention(Strict):
    """A diagnosis that was *mentioned*. Never a verified diagnosis."""
    text: str = Field(..., min_length=1, max_length=200)
    assertion: Assertion
    evidence: Optional[str] = Field(None, max_length=500)


class MedicationMention(Strict):
    """Literal mention only; creates no prescription and needs clinician/pharmacist verification."""
    text: str = Field(..., min_length=1, max_length=200)
    evidence: Optional[str] = Field(None, max_length=500)


class StaffCommitment(Strict):
    commitment: str = Field(..., min_length=1, max_length=300)
    due_text: Optional[str] = Field(None, max_length=100)
    evidence: Optional[str] = Field(None, max_length=500)


class CallbackRequest(Strict):
    raw_text: Optional[str] = Field(None, max_length=200)
    requested_date: Optional[date] = None   # only when resolvable without guessing
    evidence: Optional[str] = Field(None, max_length=500)


class AppointmentIntent(Strict):
    intent: AppointmentIntentType = AppointmentIntentType.none
    department_hint: Optional[str] = Field(None, max_length=100)
    preferred_time_text: Optional[str] = Field(None, max_length=200)
    evidence: Optional[str] = Field(None, max_length=500)


class ExtractedTask(Strict):
    title: str = Field(..., min_length=1, max_length=200)
    category: TaskCategory
    description: str = Field("", max_length=2000)
    requested_action: Optional[str] = Field(None, max_length=500)
    priority: Priority = Priority.requires_review
    priority_reason: str = Field("", max_length=500)
    evidence: Optional[str] = Field(None, max_length=500)
    due_text: Optional[str] = Field(None, max_length=100)
    requires_review: bool = False
    review_reason: str = Field("", max_length=300)
    # Free-form carry-over from the rule engine so existing urgency/negation logic is not lost.
    legacy: Optional[dict] = None


class EvidenceItem(Strict):
    field: str = Field(..., max_length=60)
    excerpt: str = Field(..., max_length=500)


class StructuredExtraction(Strict):
    schema_version: int = 1
    patient: PatientInfo = Field(default_factory=PatientInfo)
    reported_concern: Optional[str] = Field(None, max_length=500)
    symptoms: List[Symptom] = Field(default_factory=list, max_length=30)
    verified_diagnosis: Optional[str] = None      # always None - see module docstring
    diagnosis_mentions: List[DiagnosisMention] = Field(default_factory=list, max_length=20)
    medication_mentions: List[MedicationMention] = Field(default_factory=list, max_length=20)
    requested_action: Optional[str] = Field(None, max_length=500)
    department: Optional[str] = Field(None, max_length=100)   # filled by the routing service
    staff_commitments: List[StaffCommitment] = Field(default_factory=list, max_length=20)
    callback: CallbackRequest = Field(default_factory=CallbackRequest)
    appointment_intent: AppointmentIntent = Field(default_factory=AppointmentIntent)
    tasks: List[ExtractedTask] = Field(default_factory=list, max_length=20)
    priority: Priority = Priority.requires_review
    uncertainty: List[str] = Field(default_factory=list, max_length=30)
    evidence: List[EvidenceItem] = Field(default_factory=list, max_length=60)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)   # model-reported only; not a correctness proof
    review_required: bool = False
    review_reasons: List[str] = Field(default_factory=list, max_length=30)

    @field_validator("verified_diagnosis")
    @classmethod
    def _never_verified(cls, v):
        return None


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------
def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").casefold()
    return re.sub(r"\s+", " ", t).strip(" .,;:!?\"'")


def occurs_in(snippet: Optional[str], transcript_norm: str) -> bool:
    if not snippet:
        return True
    return _norm(snippet) in transcript_norm


def _add_review(ex: StructuredExtraction, reason: str) -> None:
    ex.review_required = True
    if reason not in ex.review_reasons:
        ex.review_reasons.append(reason)


def validate_extraction(raw: dict, transcript: str) -> StructuredExtraction:
    """Parse and ground-check extractor output. Raises ``ValidationError`` if malformed."""
    ex = StructuredExtraction.model_validate(raw)
    tnorm = _norm(transcript)

    # Names, identifiers, ages must be literally stated.
    if ex.patient.name and _norm(ex.patient.name) not in tnorm:
        ex.uncertainty.append("Patient name was not found verbatim in the transcript and was removed.")
        ex.patient.name = None
        _add_review(ex, "Extracted patient name could not be verified against the transcript")
    if ex.patient.patient_id and _norm(ex.patient.patient_id) not in tnorm:
        ex.uncertainty.append("Patient identifier was not found in the transcript and was removed.")
        ex.patient.patient_id = None
        _add_review(ex, "Extracted patient identifier could not be verified against the transcript")
    if ex.patient.age is not None and not re.search(rf"(?<!\d){ex.patient.age}(?!\d)", transcript):
        ex.uncertainty.append("Patient age was not stated in the transcript and was removed.")
        ex.patient.age = None
        _add_review(ex, "Extracted age could not be verified against the transcript")
    if ex.patient.date_of_birth is not None:
        y = str(ex.patient.date_of_birth.year)
        if y not in transcript:
            ex.uncertainty.append("Date of birth was not stated in the transcript and was removed.")
            ex.patient.date_of_birth = None
            _add_review(ex, "Extracted date of birth could not be verified against the transcript")

    # Medicine names may only be echoed, never invented.
    kept_meds = []
    for med in ex.medication_mentions:
        if _norm(med.text) in tnorm:
            kept_meds.append(med)
        else:
            ex.uncertainty.append("A medication mention not present in the transcript was removed.")
            _add_review(ex, "Extractor produced a medication that is not in the transcript")
    ex.medication_mentions = kept_meds
    if ex.medication_mentions:
        _add_review(ex, "Medication mentioned; verify against the prescribing record (not created from speech)")

    # Evidence excerpts must be real quotes.
    def _check(obj, label):
        if getattr(obj, "evidence", None) and not occurs_in(obj.evidence, tnorm):
            obj.evidence = None
            ex.uncertainty.append(f"Evidence for {label} was not found in the transcript and was removed.")
            _add_review(ex, f"Unverifiable evidence excerpt for {label}")

    for s in ex.symptoms:
        _check(s, "a symptom")
    for d in ex.diagnosis_mentions:
        _check(d, "a diagnosis mention")
    for c in ex.staff_commitments:
        _check(c, "a staff commitment")
    for t in ex.tasks:
        _check(t, f"task '{t.title[:40]}'")
    _check(ex.callback, "the callback request")
    _check(ex.appointment_intent, "the appointment intent")
    verified_items = []
    for item in ex.evidence:
        if occurs_in(item.excerpt, tnorm):
            verified_items.append(item)
        else:
            _add_review(ex, "Unverifiable evidence excerpt dropped")
    ex.evidence = verified_items

    # Safety invariants.
    if ex.diagnosis_mentions:
        ex.uncertainty.append("Diagnoses were mentioned but are unverified; confirm with the treating clinician.")
        _add_review(ex, "Diagnosis mentioned in conversation - unverified")
    if any(s.assertion == Assertion.possible for s in ex.symptoms):
        _add_review(ex, "Hedged or possible condition reported")
    if any(t.requires_review for t in ex.tasks):
        ex.review_required = True
    if ex.uncertainty and not ex.review_required:
        _add_review(ex, "Extractor reported uncertainty")
    if not ex.tasks and transcript.strip():
        _add_review(ex, "No actionable task could be identified")
    return ex
