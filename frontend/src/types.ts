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
  summary: string;
  created_at: string;
  status: string;
  tickets?: Ticket[];
}

export interface Scenario {
  id: string;
  title: string;
  category: string;
  caller_name: string;
  relationship: string;
  patient_name: string;
  room_number: string;
  bed: string;
  transcript: string;
  expected_requests_count: number;
  urgency_tier: UrgencyTier;
  description: string;
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
