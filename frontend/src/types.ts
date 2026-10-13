export type UrgencyTier = 'STAT_EMERGENCY' | 'URGENT' | 'ROUTINE' | 'INQUIRY';
export type TicketStatus =
  | 'PENDING'
  | 'IN_PROGRESS'
  | 'DISPATCHED'
  | 'RESOLVED'
  | 'AWAITING_REVIEW'
  | 'ASSIGNED'
  | 'AWAITING_PATIENT'
  | 'AWAITING_EXTERNAL'
  | 'CLOSED';

export const STATUS_LABELS: Record<TicketStatus, string> = {
  PENDING: 'New',
  AWAITING_REVIEW: 'Awaiting review',
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In progress',
  DISPATCHED: 'Dispatched',
  AWAITING_PATIENT: 'Awaiting patient',
  AWAITING_EXTERNAL: 'Awaiting external department',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
};

export const ALL_STATUSES = Object.keys(STATUS_LABELS) as TicketStatus[];
export const TERMINAL_STATUSES: TicketStatus[] = ['RESOLVED', 'CLOSED'];
export const isTerminalStatus = (status: TicketStatus): boolean => TERMINAL_STATUSES.includes(status);

export interface AuditLog {
  id: number;
  ticket_id: number;
  action: string;
  note: string;
  actor?: string;
  created_at: string;
}

export interface Ticket {
  id: number;
  call_id?: number;
  department: string;
  category?: string;
  intent?: string;
  title: string;
  description: string;
  raw_quote?: string;
  translated_quote?: string;
  language?: string;
  urgency: UrgencyTier;
  priority_rationale?: string;
  required_action?: string;
  explicit_deadline?: string | null;
  confidence_score?: number;
  source_timestamp?: string | null;
  status: TicketStatus;
  clinical_flags: string[];
  assigned_to: string;
  assigned_team?: string;
  assigned_staff?: string;
  is_acknowledged?: boolean;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  sla_minutes?: number;
  deadline_at?: string | null;
  is_overdue?: boolean;
  escalation_level?: number;
  escalated_at?: string | null;
  escalation_reason?: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
  resolution_notes?: string;
  is_reviewed?: boolean;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  review_notes?: string;
  room_number: string;
  patient_name: string;
  triage_notes?: string;
  patient_id?: number | null;
  task_category?: string;
  routing_reason?: string;
  requires_human_review?: boolean;
  human_review_reason?: string;
  urgency_evidence?: Record<string, any>;
  created_at: string;
  updated_at: string;
  audit_logs?: AuditLog[];
}

export interface Call {
  id: number;
  caller_name: string;
  caller_phone: string;
  patient_name: string;
  room_number: string;
  raw_transcript: string;
  language: string;
  language_confidence: number;
  translated_transcript?: string;
  summary: string;
  audio_filename?: string;
  created_at: string;
  status: string;
  tickets?: Ticket[];
  patient_id?: number | null;
  patient_match_status?: 'none' | 'needs_confirmation' | 'confirmed';
  extraction?: StructuredExtraction | null;
  extraction_provider?: string;
  source_channel?: string;
  original_asr_transcript?: string;
  transcript_edited?: boolean;
}

export interface AudioTranscribeResult {
  transcript: string;
  language: string;
  language_name: string;
  language_confidence: number;
  transcription_confidence: number;
  duration_seconds: number;
  audio_filename?: string;
  is_silent?: boolean;
  max_amplitude?: number;
  language_uncertain?: boolean;
  suggested_language?: string;
  provider?: string;
  confidence_available?: boolean;
  warnings?: string[];
  job_id?: string;
}

export interface DepartmentHandoverSummary {
  department: string;
  total_tickets: number;
  active_tickets: number;
  resolved_tickets: number;
  overdue_tickets: number;
  stat_emergency_tickets: number;
}

export interface ShiftHandoverReport {
  generated_at: string;
  shift_hours: number;
  shift_lead: string;
  total_tickets_in_shift: number;
  active_tickets: number;
  resolved_tickets: number;
  overdue_tickets_count: number;
  escalated_tickets_count: number;
  stat_emergency_count: number;
  unreviewed_flagged_count: number;
  departments: DepartmentHandoverSummary[];
  critical_alerts: Array<{
    type: string;
    ticket_id: number;
    patient: string;
    room: string;
    department: string;
    title: string;
    status?: string;
    deadline?: string;
    staff: string;
  }>;
  handover_briefing_markdown: string;
}

export interface AnalyticsData {
  total_calls: number;
  total_tickets: number;
  emergency_count: number;
  urgent_count: number;
  routine_count: number;
  inquiry_count: number;
  pending_tickets: number;
  in_progress_tickets: number;
  resolved_tickets: number;
  overdue_tickets?: number;
  escalated_tickets?: number;
  unacknowledged_tickets?: number;
  unreviewed_tickets?: number;
  department_distribution: Record<string, number>;
  urgency_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  languages_detected?: Record<string, number>;
  avg_triage_latency_ms: number;
  system_mode: string;
}

export interface ProcessCallResult {
  call: Call;
  extracted_tickets: Ticket[];
  emergency_detected: boolean;
  summary: string;
  engine_used: string;
  structured_extraction?: StructuredExtraction | null;
  patient_match_candidates?: PatientCandidate[];
  extraction_warnings?: string[];
}

// ---------------------------------------------------------------- structured extraction
export type Assertion = 'reported' | 'negated' | 'possible';

export interface StructuredExtraction {
  patient: {
    name: string | null;
    patient_id: string | null;
    age: number | null;
    date_of_birth: string | null;
    caller_relationship: string | null;
  };
  reported_concern: string | null;
  symptoms: Array<{ text: string; assertion: Assertion; evidence?: string | null }>;
  verified_diagnosis: null;
  diagnosis_mentions: Array<{ text: string; assertion: Assertion; evidence?: string | null }>;
  medication_mentions: Array<{ text: string; evidence?: string | null }>;
  requested_action: string | null;
  department: string | null;
  staff_commitments: Array<{ commitment: string; due_text?: string | null; evidence?: string | null }>;
  callback: { raw_text: string | null; requested_date: string | null; evidence?: string | null };
  appointment_intent: { intent: 'none' | 'book' | 'reschedule' | 'cancel' | 'follow_up'; evidence?: string | null };
  tasks: Array<{ title: string; category: string; priority: string; requires_review: boolean; evidence?: string | null }>;
  priority: 'emergency' | 'urgent' | 'routine' | 'inquiry' | 'requires_review';
  uncertainty: string[];
  confidence: number | null;
  review_required: boolean;
  review_reasons: string[];
}

export interface PatientCandidate {
  patient_id: number;
  patient_uid: string;
  display_name: string;
  score: number;
  confidence_band: 'high' | 'medium' | 'low';
  signals: string[];
  identity_verified: boolean;
}

// ---------------------------------------------------------------- auth
export type Role = 'admin' | 'nurse' | 'clinician' | 'coordinator' | 'pharmacist' | 'patient';

export interface SessionUser {
  id: number;
  username: string;
  full_name: string;
  role: Role;
  department?: string | null;
  patient_id?: number | null;
  permissions: string[];
}

// ---------------------------------------------------------------- speech-to-text
export interface AsrLanguage {
  code: string;
  name: string;
  available: boolean;
  providers: Array<{ name: string; available: boolean }>;
}

export interface AsrStatus {
  providers: Array<{ name: string; available: boolean; reason: string; languages: string[]; language_detection: boolean }>;
  languages: AsrLanguage[];
  limits: { max_upload_mb: number; max_duration_seconds: number; audio_retention_hours: number };
  extraction_provider: string;
  notes: string[];
}

// ---------------------------------------------------------------- patients
export interface PatientSummary {
  id: number;
  patient_uid: string;
  full_name: string;
  mrn: string | null;
  date_of_birth: string | null;
  identity_verified: boolean;
}

export interface Patient extends PatientSummary {
  sex: string | null;
  phone: string | null;
  email: string | null;
  preferred_language: string | null;
  contact_preference: string;
  status: string;
  created_at: string;
}

export interface ClinicalRecord {
  id: number;
  record_type: 'allergy' | 'condition' | 'history' | 'note';
  description: string;
  severity: string | null;
  source: string;
  recorded_at: string;
  entered_in_error: boolean;
}

export interface Medication {
  id: number;
  patient_id: number;
  medicine: string;
  dose: string;
  route: string;
  frequency: string;
  duration: string | null;
  prescriber_name: string;
  prescription_ref: string | null;
  source: string;
  effective_from: string;
  effective_to: string | null;
  status: 'active' | 'stopped' | 'superseded' | 'entered_in_error';
  supersedes_id: number | null;
  verified_at: string;
}

// ---------------------------------------------------------------- scheduling
export interface Slot {
  id: number;
  clinician_id: number;
  clinician_name: string;
  department: string;
  specialty: string | null;
  location: string;
  start_local: string;
  end_local: string;
  start_utc: string;
  status: string;
}

export type AppointmentStatus = 'requested' | 'pending' | 'confirmed' | 'cancelled' | 'completed';

export interface Appointment {
  id: number;
  patient_id: number;
  status: AppointmentStatus;
  department: string;
  reason: string | null;
  slot: Slot | null;
  change_request: 'reschedule' | 'cancel' | null;
  change_request_note: string | null;
  created_at: string;
}

export interface RoutingRule {
  id: number;
  name: string;
  priority: number;
  match_category: string | null;
  match_urgency: string | null;
  match_keyword: string | null;
  target_team: string;
  is_active: boolean;
}

export interface RoutingPolicy {
  sla_minutes: Record<string, number>;
  fallback_team: string;
  emergency_team: string;
  emergency_instruction: string;
  task_categories: string[];
  default_teams: Record<string, string>;
}

export interface AuditEventRow {
  id: number;
  occurred_at: string;
  actor_user_id: number | null;
  actor_role: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  patient_id: number | null;
  outcome: string;
  detail: Record<string, unknown>;
}
