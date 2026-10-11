from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

class CallCreate(BaseModel):
    caller_name: Optional[str] = "Unknown Caller"
    caller_phone: Optional[str] = ""
    patient_name: Optional[str] = "Unknown Patient"
    room_number: Optional[str] = "Unassigned"
    raw_transcript: str = Field(..., min_length=2, description="Speech transcript in original language")
    language: Optional[str] = "en"
    language_confidence: Optional[float] = 1.0
    translated_transcript: Optional[str] = ""
    audio_filename: Optional[str] = ""

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticket_id: int
    action: str
    note: Optional[str] = ""
    created_at: datetime

class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    call_id: Optional[int] = None
    department: str
    title: str
    description: str
    raw_quote: Optional[str] = ""
    translated_quote: Optional[str] = ""
    language: Optional[str] = "en"
    urgency: str
    status: str
    clinical_flags: List[str] = []
    assigned_to: str
    room_number: str
    patient_name: str
    triage_notes: Optional[str] = ""
    created_at: datetime
    updated_at: datetime
    audit_logs: List[AuditLogResponse] = []

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    department: Optional[str] = None
    assigned_to: Optional[str] = None
    triage_notes: Optional[str] = None

class TicketNoteCreate(BaseModel):
    note: str = Field(..., min_length=1)
    author: Optional[str] = "Staff Member"

class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    caller_name: str
    caller_phone: str
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
    department_distribution: Dict[str, int]
    urgency_distribution: Dict[str, int]
    status_distribution: Dict[str, int]
    languages_detected: Dict[str, int]
    avg_triage_latency_ms: float
    system_mode: str
