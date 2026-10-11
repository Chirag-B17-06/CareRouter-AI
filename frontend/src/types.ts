export type UrgencyTier = 'STAT_EMERGENCY' | 'URGENT' | 'ROUTINE' | 'INQUIRY';
export type TicketStatus = 'PENDING' | 'IN_PROGRESS' | 'DISPATCHED' | 'RESOLVED';

export interface AuditLog {
  id: number;
  ticket_id: number;
  action: string;
  note: string;
  created_at: string;
}

export interface Ticket {
  id: number;
  call_id?: number;
  department: string;
  title: string;
  description: string;
  raw_quote?: string;
  translated_quote?: string;
  language?: string;
  urgency: UrgencyTier;
  status: TicketStatus;
  clinical_flags: string[];
  assigned_to: string;
  room_number: string;
  patient_name: string;
  triage_notes?: string;
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
