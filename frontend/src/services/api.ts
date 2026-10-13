import {
  Ticket, Call, AnalyticsData, ProcessCallResult, TicketStatus, AudioTranscribeResult, ShiftHandoverReport,
  SessionUser, AsrStatus, PatientCandidate,
} from '../types';
import { decodeBrowserAudioToWav } from '../utils/audio';
import { getToken, saveSession, clearSession, SESSION_EXPIRED_EVENT } from './session';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/** Thrown for non-2xx responses. `message` is safe to show to the user. */
export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/**
 * fetch() with the bearer token attached.  A 401 means the session is gone (expired, signed out
 * elsewhere, account disabled): the stored session is cleared and the app returns to sign-in.
 */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(input, { ...init, headers });
  if (res.status === 401 && !input.endsWith('/api/auth/login')) {
    clearSession();
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
  return res;
}

export function formatApiErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === 'object' && item && 'msg' in item ? String((item as { msg: unknown }).msg) : String(item)))
      .join('; ');
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: unknown }).message);
  }
  return fallback;
}

async function toError(res: Response, fallback: string): Promise<ApiError> {
  let detail: unknown = undefined;
  try {
    detail = (await res.json()).detail;
  } catch {
    /* body was not JSON */
  }
  if (res.status === 403) return new ApiError('You do not have permission to do that.', 403, detail);
  if (res.status === 429) return new ApiError(formatApiErrorDetail(detail, 'Too many requests. Please wait a moment.'), 429, detail);
  return new ApiError(formatApiErrorDetail(detail, fallback), res.status, detail);
}

/** JSON request helper used by the newer endpoints. */
export async function api<T>(path: string, options: { method?: string; body?: unknown; fallback?: string } = {}): Promise<T> {
  const res = await apiFetch(`${API_BASE}${path}`, {
    method: options.method ?? 'GET',
    headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) throw await toError(res, options.fallback ?? 'Request failed');
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------- authentication
export async function login(username: string, password: string): Promise<SessionUser> {
  const res = await apiFetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw await toError(res, 'Sign-in failed');
  const body = await res.json();
  saveSession(body.access_token, body.user);
  return body.user as SessionUser;
}

export async function logout(): Promise<void> {
  try {
    await apiFetch(`${API_BASE}/api/auth/logout`, { method: 'POST' });
  } catch {
    /* signing out locally is what matters */
  }
  clearSession();
}

export async function fetchMe(): Promise<SessionUser> {
  return api<SessionUser>('/api/auth/me', { fallback: 'Could not load your session' });
}

export async function fetchHealth(): Promise<{
  status: string;
  stt_engine: string;
  supported_languages: Record<string, string>;
}> {
  const res = await apiFetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

// ---------------------------------------------------------------- speech-to-text
export function fetchAsrStatus(): Promise<AsrStatus> {
  return api<AsrStatus>('/api/asr/status', { fallback: 'Could not load speech engine status' });
}

export type TranscribeProgress = (state: 'uploading' | 'queued' | 'running') => void;

/**
 * Upload audio and wait for the background transcription job.  Inference runs on the server in a
 * worker; this just polls the job (so a long recording never hits a request timeout).
 * `recordingConsent` must be true or the server refuses to process the audio.
 */
export async function uploadAndTranscribeAudio(
  audioBlobOrFile: Blob | File,
  language: string | undefined,
  filename: string = 'recording.webm',
  options: { recordingConsent: boolean; onProgress?: TranscribeProgress; signal?: AbortSignal } = { recordingConsent: false },
): Promise<AudioTranscribeResult> {
  let payload: Blob = audioBlobOrFile;
  let uploadName = filenameFromMime(audioBlobOrFile.type, filename);

  // Re-encode in the browser to 16 kHz WAV so the server is not given Chrome MediaRecorder
  // timeslice WebM (often unreadable after InvalidDataError skips).
  try {
    payload = await decodeBrowserAudioToWav(audioBlobOrFile);
    uploadName = uploadName.replace(/\.[^.]+$/, '') + '.wav';
  } catch (err) {
    console.warn('WAV re-encode failed; uploading original audio', err);
  }

  const formData = new FormData();
  formData.append('audio_file', payload, uploadName);
  formData.append('recording_consent', options.recordingConsent ? 'true' : 'false');
  if (language && language !== 'auto') formData.append('language', language);

  options.onProgress?.('uploading');
  const res = await apiFetch(`${API_BASE}/api/audio/jobs`, { method: 'POST', body: formData, signal: options.signal });
  if (!res.ok) throw await toError(res, 'Failed to upload audio');
  const { job_id } = (await res.json()) as { job_id: string };

  const started = Date.now();
  let delay = 700;
  for (;;) {
    if (options.signal?.aborted) throw new ApiError('Transcription cancelled', 0);
    const poll = await apiFetch(`${API_BASE}/api/audio/jobs/${job_id}`, { signal: options.signal });
    if (!poll.ok) throw await toError(poll, 'Could not read transcription status');
    const job = await poll.json();
    if (job.status === 'succeeded') {
      return { ...(job.result as AudioTranscribeResult), job_id, audio_filename: job.audio_retained ? job.result?.audio_filename : '' };
    }
    if (job.status === 'failed') {
      throw new ApiError(job.error_message || 'Speech recognition failed', 422, { code: job.error_code });
    }
    options.onProgress?.(job.status === 'running' ? 'running' : 'queued');
    if (Date.now() - started > 15 * 60 * 1000) throw new ApiError('Transcription is taking too long. Please retry.', 408);
    await new Promise((r) => setTimeout(r, delay));
    delay = Math.min(delay * 1.4, 4000);
  }
}

export async function processTranscript(data: {
  raw_transcript: string;
  language?: string;
  caller_name?: string;
  caller_phone?: string;
  patient_name?: string;
  room_number?: string;
  audio_filename?: string;
  patient_id?: number;
  source_channel?: 'microphone' | 'upload' | 'manual';
  recording_consent?: boolean;
  transcription_job_id?: string;
  original_asr_transcript?: string;
  idempotency_key?: string;
}): Promise<ProcessCallResult> {
  const res = await apiFetch(`${API_BASE}/api/calls/process-transcript`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await toError(res, 'Failed to process transcript');
  return res.json();
}

export function confirmPatientLink(callId: number, patientId: number) {
  return api<{ message: string }>(`/api/conversations/${callId}/link-patient`, {
    method: 'POST', body: { patient_id: patientId }, fallback: 'Could not link the patient',
  });
}

export function unlinkPatient(callId: number) {
  return api<{ message: string }>(`/api/conversations/${callId}/unlink-patient`, { method: 'POST' });
}

export function fetchCallCandidates(callId: number) {
  return api<PatientCandidate[]>(`/api/conversations/${callId}/patient-candidates`);
}

/** Fetch an authenticated binary (audio / export) and return an object URL. */
export async function fetchBlobUrl(path: string): Promise<string> {
  const res = await apiFetch(`${API_BASE}${path}`);
  if (!res.ok) throw await toError(res, 'Could not load the file');
  return URL.createObjectURL(await res.blob());
}

function filenameFromMime(mime: string, fallback: string): string {
  const type = (mime || '').toLowerCase();
  if (type.includes('wav')) return fallback.replace(/\.[^.]+$/, '') + '.wav';
  if (type.includes('mp4') || type.includes('m4a')) return fallback.replace(/\.[^.]+$/, '') + '.m4a';
  if (type.includes('ogg')) return fallback.replace(/\.[^.]+$/, '') + '.ogg';
  if (type.includes('mpeg') || type.includes('mp3')) return fallback.replace(/\.[^.]+$/, '') + '.mp3';
  if (type.includes('webm')) return fallback.replace(/\.[^.]+$/, '') + '.webm';
  return fallback;
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
  const res = await apiFetch(url);
  if (!res.ok) throw new Error('Failed to fetch tickets');
  return res.json();
}

export async function fetchTicket(id: number): Promise<Ticket> {
  const res = await apiFetch(`${API_BASE}/api/tickets/${id}`);
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
  const res = await apiFetch(`${API_BASE}/api/tickets/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to update ticket');
  return res.json();
}

export async function acknowledgeTicket(id: number, acknowledged_by: string = 'Staff Member'): Promise<Ticket> {
  const res = await apiFetch(`${API_BASE}/api/tickets/${id}/acknowledge`, {
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
  const res = await apiFetch(`${API_BASE}/api/tickets/${id}/assign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to assign ticket');
  return res.json();
}

export async function escalateTicket(id: number, reason: string, escalated_by: string = 'Charge Nurse', level?: number): Promise<Ticket> {
  const res = await apiFetch(`${API_BASE}/api/tickets/${id}/escalate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ escalation_reason: reason, escalated_by, level })
  });
  if (!res.ok) throw new Error('Failed to escalate ticket');
  return res.json();
}

export async function resolveTicket(id: number, resolution_notes: string, resolved_by: string = 'Staff Member'): Promise<Ticket> {
  const res = await apiFetch(`${API_BASE}/api/tickets/${id}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolution_notes, resolved_by })
  });
  if (!res.ok) throw new Error('Failed to resolve ticket');
  return res.json();
}

export async function checkEscalations(): Promise<{ message: string; escalated_count: number }> {
  const res = await apiFetch(`${API_BASE}/api/tickets/check-escalations`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to check escalations');
  return res.json();
}

export async function deleteTicket(id: number): Promise<{ message: string }> {
  const res = await apiFetch(`${API_BASE}/api/tickets/${id}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete ticket');
  return res.json();
}

export async function addTicketNote(id: number, note: string, author: string = 'Staff'): Promise<Ticket> {
  const res = await apiFetch(`${API_BASE}/api/tickets/${id}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note, author })
  });
  if (!res.ok) throw new Error('Failed to add note');
  return res.json();
}

export async function fetchCalls(): Promise<Call[]> {
  const res = await apiFetch(`${API_BASE}/api/calls`);
  if (!res.ok) throw new Error('Failed to fetch calls');
  return res.json();
}

export async function fetchCall(callId: number): Promise<Call> {
  const res = await apiFetch(`${API_BASE}/api/calls/${callId}`);
  if (!res.ok) throw new Error('Failed to fetch call record');
  return res.json();
}

export async function deleteCall(callId: number): Promise<{ message: string }> {
  const res = await apiFetch(`${API_BASE}/api/calls/${callId}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete call');
  return res.json();
}

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const res = await apiFetch(`${API_BASE}/api/analytics`);
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
  const res = await apiFetch(`${API_BASE}/api/tickets/${id}/review`, {
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
  const res = await apiFetch(`${API_BASE}/api/reports/shift-handover?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch shift handover report');
  return res.json();
}

