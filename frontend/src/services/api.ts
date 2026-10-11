import { Ticket, Call, Scenario, AnalyticsData, ProcessCallResult, TicketStatus } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export async function fetchHealth(): Promise<{ status: string; demo_mode: boolean; engine: string }> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchScenarios(): Promise<Scenario[]> {
  const res = await fetch(`${API_BASE}/api/scenarios`);
  if (!res.ok) throw new Error('Failed to fetch scenarios');
  return res.json();
}

export async function processCall(data: {
  raw_transcript: string;
  caller_name?: string;
  caller_phone?: string;
  patient_name?: string;
  room_number?: string;
}): Promise<ProcessCallResult> {
  const res = await fetch(`${API_BASE}/api/calls/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to process call: ${errorText}`);
  }
  return res.json();
}

export async function fetchTickets(filters?: {
  department?: string;
  urgency?: string;
  status?: string;
  search?: string;
}): Promise<Ticket[]> {
  const params = new URLSearchParams();
  if (filters?.department && filters.department !== 'All') params.append('department', filters.department);
  if (filters?.urgency && filters.urgency !== 'All') params.append('urgency', filters.urgency);
  if (filters?.status && filters.status !== 'All') params.append('status', filters.status);
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

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const res = await fetch(`${API_BASE}/api/analytics`);
  if (!res.ok) throw new Error('Failed to fetch analytics');
  return res.json();
}

export async function resetDemoDatabase(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/demo/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset database');
  return res.json();
}
