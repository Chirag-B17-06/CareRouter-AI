import { Ticket, Call, AnalyticsData, ProcessCallResult, TicketStatus, AudioTranscribeResult, ShiftHandoverReport } from '../types';
import { decodeBrowserAudioToWav } from '../utils/audio';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

function filenameFromMime(mime: string, fallback: string): string {
  const type = (mime || '').toLowerCase();
  if (type.includes('wav')) return fallback.replace(/\.[^.]+$/, '') + '.wav';
  if (type.includes('mp4') || type.includes('m4a')) return fallback.replace(/\.[^.]+$/, '') + '.m4a';
  if (type.includes('ogg')) return fallback.replace(/\.[^.]+$/, '') + '.ogg';
  if (type.includes('mpeg') || type.includes('mp3')) return fallback.replace(/\.[^.]+$/, '') + '.mp3';
  if (type.includes('webm')) return fallback.replace(/\.[^.]+$/, '') + '.webm';
  return fallback;
}

function formatApiErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === 'object' && item && 'msg' in item ? String((item as { msg: unknown }).msg) : String(item)))
      .join('; ');
  }
  return fallback;
}

export async function fetchHealth(): Promise<{
  status: string;
  stt_engine: string;
  supported_languages: Record<string, string>;
}> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function uploadAndTranscribeAudio(
  audioBlobOrFile: Blob | File,
  language?: string,
  filename: string = 'recording.webm'
): Promise<AudioTranscribeResult> {
  let payload: Blob = audioBlobOrFile;
  let uploadName = filenameFromMime(audioBlobOrFile.type, filename);

  // Re-encode in the browser to 16 kHz WAV so Whisper/PyAV is not given
  // Chrome MediaRecorder timeslice WebM (often empty after InvalidDataError skips).
  try {
    payload = await decodeBrowserAudioToWav(audioBlobOrFile);
    uploadName = uploadName.replace(/\.[^.]+$/, '') + '.wav';
  } catch (err) {
    console.warn('WAV re-encode failed; uploading original audio', err);
  }

  const formData = new FormData();
  formData.append('audio_file', payload, uploadName);
  if (language && language !== 'auto') {
    formData.append('language', language);
  }

  const res = await fetch(`${API_BASE}/api/audio/transcribe`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    let errorMsg = 'Failed to transcribe audio';
    try {
      const errorJson = await res.json();
      errorMsg = formatApiErrorDetail(errorJson.detail, errorMsg);
    } catch {
      errorMsg = await res.text();
    }
    throw new Error(errorMsg);
  }

  return res.json();
}

export async function processTranscript(data: {
  raw_transcript: string;
  language?: string;
  caller_name?: string;
  caller_phone?: string;
  patient_name?: string;
  room_number?: string;
  audio_filename?: string;
}): Promise<ProcessCallResult> {
  const res = await fetch(`${API_BASE}/api/calls/process-transcript`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    let errorMsg = 'Failed to process transcript';
    try {
      const err = await res.json();
      errorMsg = err.detail || errorMsg;
    } catch {
      errorMsg = await res.text();
    }
    throw new Error(errorMsg);
  }
  return res.json();
}

export async function fetchTickets(filters?: {
  department?: string;
  urgency?: string;
  status?: string;
  language?: string;
  search?: string;
  is_overdue?: boolean;
  is_acknowledged?: boolean;
  escalation_level?: number;
  requires_human_review?: boolean;
  is_reviewed?: boolean;
}): Promise<Ticket[]> {
  const params = new URLSearchParams();
  if (filters?.department && filters.department !== 'All') params.append('department', filters.department);
  if (filters?.urgency && filters.urgency !== 'All') params.append('urgency', filters.urgency);
  if (filters?.status && filters.status !== 'All') params.append('status', filters.status);
  if (filters?.language && filters.language !== 'All') params.append('language', filters.language);
  if (filters?.search) params.append('search', filters.search);
  if (filters?.is_overdue !== undefined) params.append('is_overdue', String(filters.is_overdue));
  if (filters?.is_acknowledged !== undefined) params.append('is_acknowledged', String(filters.is_acknowledged));
  if (filters?.escalation_level !== undefined) params.append('escalation_level', String(filters.escalation_level));
  if (filters?.requires_human_review !== undefined) params.append('requires_human_review', String(filters.requires_human_review));
  if (filters?.is_reviewed !== undefined) params.append('is_reviewed', String(filters.is_reviewed));

  const url = `${API_BASE}/api/tickets${params.toString() ? '?' + params.toString() : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch tickets');
  return res.json();
}

export async function fetchTicket(id: number): Promise<Ticket> {
  const res = await fetch(`${API_BASE}/api/tickets/${id}`);
  if (!res.ok) throw new Error('Failed to fetch ticket');
  return res.json();
}

export async function updateTicket(id: number, payload: {
  status?: TicketStatus;
  department?: string;
  assigned_to?: string;
  assigned_team?: string;
  assigned_staff?: string;
  triage_notes?: string;
}): Promise<Ticket> {
  const res = await fetch(`${API_BASE}/api/tickets/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to update ticket');
  return res.json();
}

export async function acknowledgeTicket(id: number, acknowledged_by: string = 'Staff Member'): Promise<Ticket> {
  const res = await fetch(`${API_BASE}/api/tickets/${id}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ acknowledged_by })
  });
  if (!res.ok) throw new Error('Failed to acknowledge ticket');
  return res.json();
}

export async function assignTicket(id: number, payload: {
  assigned_staff?: string;
  assigned_team?: string;
  assigned_to?: string;
  assigner?: string;
}): Promise<Ticket> {
  const res = await fetch(`${API_BASE}/api/tickets/${id}/assign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to assign ticket');
  return res.json();
}

export async function escalateTicket(id: number, reason: string, escalated_by: string = 'Charge Nurse', level?: number): Promise<Ticket> {
  const res = await fetch(`${API_BASE}/api/tickets/${id}/escalate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ escalation_reason: reason, escalated_by, level })
  });
  if (!res.ok) throw new Error('Failed to escalate ticket');
  return res.json();
}

export async function resolveTicket(id: number, resolution_notes: string, resolved_by: string = 'Staff Member'): Promise<Ticket> {
  const res = await fetch(`${API_BASE}/api/tickets/${id}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolution_notes, resolved_by })
  });
  if (!res.ok) throw new Error('Failed to resolve ticket');
  return res.json();
}

export async function checkEscalations(): Promise<{ message: string; escalated_count: number }> {
  const res = await fetch(`${API_BASE}/api/tickets/check-escalations`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to check escalations');
  return res.json();
}

export async function deleteTicket(id: number): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/tickets/${id}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete ticket');
  return res.json();
}

export async function addTicketNote(id: number, note: string, author: string = 'Staff'): Promise<Ticket> {
  const res = await fetch(`${API_BASE}/api/tickets/${id}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note, author })
  });
  if (!res.ok) throw new Error('Failed to add note');
  return res.json();
}

export async function fetchCalls(): Promise<Call[]> {
  const res = await fetch(`${API_BASE}/api/calls`);
  if (!res.ok) throw new Error('Failed to fetch calls');
  return res.json();
}

export async function fetchCall(callId: number): Promise<Call> {
  const res = await fetch(`${API_BASE}/api/calls/${callId}`);
  if (!res.ok) throw new Error('Failed to fetch call record');
  return res.json();
}

export async function deleteCall(callId: number): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/calls/${callId}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete call');
  return res.json();
}

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const res = await fetch(`${API_BASE}/api/analytics`);
  if (!res.ok) throw new Error('Failed to fetch analytics');
  return res.json();
}

export async function reviewTicket(
  id: number,
  payload: {
    reviewer_name: string;
    action: 'APPROVE' | 'CORRECT';
    review_notes?: string;
    corrected_urgency?: string;
    corrected_department?: string;
    corrected_title?: string;
    corrected_action?: string;
  }
): Promise<Ticket> {
  const res = await fetch(`${API_BASE}/api/tickets/${id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    let errorMsg = 'Failed to submit clinical review';
    try {
      const err = await res.json();
      errorMsg = err.detail || errorMsg;
    } catch {
      errorMsg = await res.text();
    }
    throw new Error(errorMsg);
  }
  return res.json();
}

export async function fetchShiftHandoverReport(
  shift_hours: number = 8,
  shift_lead: string = 'Charge Nurse on Duty'
): Promise<ShiftHandoverReport> {
  const params = new URLSearchParams({
    shift_hours: String(shift_hours),
    shift_lead
  });
  const res = await fetch(`${API_BASE}/api/reports/shift-handover?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch shift handover report');
  return res.json();
}

export function getExportTicketsUrl(format: 'json' | 'csv' = 'csv', deIdentify: boolean = false): string {
  const params = new URLSearchParams({ format });
  if (deIdentify) params.append('de_identify', 'true');
  return `${API_BASE}/api/export/tickets?${params.toString()}`;
}

export function getAudioFileUrl(filename: string): string {
  return `${API_BASE}/api/audio/${encodeURIComponent(filename)}`;
}
