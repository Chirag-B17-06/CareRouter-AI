from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class CallCreate(BaseModel):
    idempotency_key: Optional[str] = Field(None, description="Client-provided idempotency key for retry deduplication")
    caller_name: Optional[str] = "Unknown Caller"
    caller_phone: Optional[str] = ""
    patient_name: Optional[str] = "Unknown Patient"
    room_number: Optional[str] = "Unassigned"
    raw_transcript: str = Field(..., description="Speech transcript in original language")
    language: Optional[str] = "en"
    language_confidence: Optional[float] = 1.0
    translated_transcript: Optional[str] = ""
    audio_filename: Optional[str] = ""

    @field_validator("caller_name", "patient_name", "room_number")
    @classmethod
    def clean_strings(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    ticket_id: int
    action: str
    note: Optional[str] = ""
    actor: Optional[str] = "Clinical Staff"
    created_at: Optional[datetime] = None

class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    call_id: Optional[int] = None
    department: str
    category: Optional[str] = "Nursing and patient care"
    intent: Optional[str] = "general_request"
    title: str
    description: str
    raw_quote: Optional[str] = ""
    translated_quote: Optional[str] = ""
    language: Optional[str] = "en"
    urgency: str
    priority_rationale: Optional[str] = ""
    required_action: Optional[str] = ""
    explicit_deadline: Optional[str] = None
    confidence_score: Optional[float] = 1.0
    source_timestamp: Optional[str] = None
    requires_human_review: Optional[bool] = False
    human_review_reason: Optional[str] = ""
    is_reviewed: Optional[bool] = False
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = ""
    urgency_evidence: Optional[Dict[str, Any]] = None
    status: str
    clinical_flags: List[str] = []
    assigned_to: str
    assigned_team: Optional[str] = "Rapid Response & Critical Nursing"
    assigned_staff: Optional[str] = "Unassigned"
    is_acknowledged: Optional[bool] = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    sla_minutes: Optional[int] = 60
    deadline_at: Optional[datetime] = None
    is_overdue: Optional[bool] = False
    escalation_level: Optional[int] = 0
    escalated_at: Optional[datetime] = None
    escalation_reason: Optional[str] = ""
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = ""
    room_number: str
    patient_name: str
    triage_notes: Optional[str] = ""
    created_at: datetime
    updated_at: datetime
    audit_logs: List[AuditLogResponse] = []

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    department: Optional[str] = None
    category: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_team: Optional[str] = None
    assigned_staff: Optional[str] = None
    priority_rationale: Optional[str] = None
    required_action: Optional[str] = None
    explicit_deadline: Optional[str] = None
    requires_human_review: Optional[bool] = None
    human_review_reason: Optional[str] = None
    triage_notes: Optional[str] = None
    is_acknowledged: Optional[bool] = None
    acknowledged_by: Optional[str] = None
    escalation_level: Optional[int] = None
    escalation_reason: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None

class TicketAcknowledgeRequest(BaseModel):
    acknowledged_by: Optional[str] = "Staff Member"

class TicketEscalateRequest(BaseModel):
    escalation_reason: str = Field(..., min_length=2)
    escalated_by: Optional[str] = "Staff Supervisor"
    level: Optional[int] = None

class TicketResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=2)
    resolved_by: Optional[str] = "Staff Member"

class TicketAssignRequest(BaseModel):
    assigned_staff: Optional[str] = None
    assigned_team: Optional[str] = None
    assigned_to: Optional[str] = None
    assigner: Optional[str] = "Care Coordinator"

class TicketNoteCreate(BaseModel):
    note: str = Field(..., min_length=1)
    author: Optional[str] = "Staff Member"

class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    idempotency_key: Optional[str] = None
    caller_name: str
    caller_phone: str
    masked_caller_phone: Optional[str] = ""
    patient_name: str
    room_number: str
    raw_transcript: str
    language: str
    language_confidence: float
    translated_transcript: Optional[str] = ""
    summary: str
    audio_filename: Optional[str] = ""
    created_at: datetime
    status: str
    tickets: List[TicketResponse] = []

class ProcessCallResponse(BaseModel):
    call: CallResponse
    extracted_tickets: List[TicketResponse]
    emergency_detected: bool
    summary: str
    engine_used: str

class AudioTranscribeResponse(BaseModel):
    transcript: str
    language: str
    language_name: str
    language_confidence: float
    transcription_confidence: float
    duration_seconds: float
    audio_filename: Optional[str] = ""
    is_silent: Optional[bool] = False
    max_amplitude: Optional[float] = 0.0
    language_uncertain: Optional[bool] = False
    suggested_language: Optional[str] = None

class TicketReviewRequest(BaseModel):
    reviewer_name: str = "Clinician Reviewer"
    action: str = Field(..., description="'APPROVE' or 'CORRECT'")
    review_notes: Optional[str] = ""
    corrected_urgency: Optional[str] = None
    corrected_department: Optional[str] = None
    corrected_title: Optional[str] = None
    corrected_action: Optional[str] = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        act = v.strip().upper()
        if act not in ("APPROVE", "CORRECT"):
            raise ValueError("Review action must be 'APPROVE' or 'CORRECT'")
        return act

class DepartmentHandoverSummary(BaseModel):
    department: str
    total_tickets: int
    active_tickets: int
    resolved_tickets: int
    overdue_tickets: int
    stat_emergency_tickets: int

class ShiftHandoverResponse(BaseModel):
    generated_at: datetime
    shift_hours: int
    shift_lead: str
    total_tickets_in_shift: int
    active_tickets: int
    resolved_tickets: int
    overdue_tickets_count: int
    escalated_tickets_count: int
    stat_emergency_count: int
    unreviewed_flagged_count: int
    departments: List[DepartmentHandoverSummary]
    critical_alerts: List[Dict[str, Any]]
    handover_briefing_markdown: str

class AnalyticsResponse(BaseModel):
    total_calls: int
    total_tickets: int
    emergency_count: int
    urgent_count: int
    routine_count: int
    inquiry_count: int
    pending_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    overdue_tickets: Optional[int] = 0
    escalated_tickets: Optional[int] = 0
    unacknowledged_tickets: Optional[int] = 0
    unreviewed_tickets: Optional[int] = 0
    department_distribution: Dict[str, int]
    urgency_distribution: Dict[str, int]
    status_distribution: Dict[str, int]
    languages_detected: Dict[str, int]
    avg_triage_latency_ms: float
    system_mode: str
