export type UrgencyTier = 'STAT_EMERGENCY' | 'URGENT' | 'ROUTINE' | 'INQUIRY';
export type TicketStatus = 'PENDING' | 'IN_PROGRESS' | 'DISPATCHED' | 'RESOLVED';

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
}
