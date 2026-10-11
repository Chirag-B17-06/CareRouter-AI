import { Ticket, Call, AnalyticsData, ProcessCallResult, TicketStatus, AudioTranscribeResult } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

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
  const formData = new FormData();
  formData.append('audio_file', audioBlobOrFile, filename);
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
      errorMsg = errorJson.detail || errorMsg;
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
