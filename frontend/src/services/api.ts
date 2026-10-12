import { Ticket, Call, AnalyticsData, ProcessCallResult, TicketStatus, AudioTranscribeResult } from '../types';
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
}): Promise<Ticket[]> {
  const params = new URLSearchParams();
  if (filters?.department && filters.department !== 'All') params.append('department', filters.department);
  if (filters?.urgency && filters.urgency !== 'All') params.append('urgency', filters.urgency);
  if (filters?.status && filters.status !== 'All') params.append('status', filters.status);
  if (filters?.language && filters.language !== 'All') params.append('language', filters.language);
  if (filters?.search) params.append('search', filters.search);

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
