// API calls for the patient-coordination features (patients, scheduling, portal, admin).
import {
  Appointment, AuditEventRow, ClinicalRecord, Medication, Patient, PatientCandidate, PatientSummary,
  RoutingPolicy, RoutingRule, Slot,
} from '../types';
import { api, apiFetch } from './api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.append(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : '';
};

// ---------------------------------------------------------------- patients
export const searchPatients = (q: string, page = 1, pageSize = 15) =>
  api<Page<PatientSummary>>(`/api/patients${qs({ q, page, page_size: pageSize })}`, { fallback: 'Patient search failed' });

export const getPatient = (id: number) => api<Patient>(`/api/patients/${id}`);

export type NewPatient = {
  full_name: string;
  mrn?: string;
  date_of_birth?: string;
  sex?: string;
  phone?: string;
  email?: string;
  preferred_language?: string;
  contact_preference?: string;
  confirm_not_duplicate?: boolean;
};

export const createPatient = (body: NewPatient) =>
  api<Patient>('/api/patients', { method: 'POST', body, fallback: 'Could not create patient' });

export const verifyPatient = (id: number) => api<Patient>(`/api/patients/${id}/verify`, { method: 'POST' });

export const matchPatients = (body: { name?: string; date_of_birth?: string; age?: number; phone?: string; mrn?: string }) =>
  api<PatientCandidate[]>('/api/patients/match', { method: 'POST', body });

export const patientTimeline = (id: number) =>
  api<{
    conversations: Array<{ id: number; created_at: string; summary: string; language: string }>;
    tasks: Array<{ id: number; title: string; status: string; urgency: string; assigned_team: string; created_at: string }>;
    appointments: Array<{ id: number; status: string; department: string; created_at: string }>;
  }>(`/api/patients/${id}/timeline`);

export const listClinical = (id: number) => api<ClinicalRecord[]>(`/api/patients/${id}/clinical`);
export const addClinical = (id: number, body: { record_type: string; description: string; severity?: string }) =>
  api<ClinicalRecord>(`/api/patients/${id}/clinical`, { method: 'POST', body, fallback: 'Could not save the record' });

export const listMedications = (id: number, history = false) =>
  api<Medication[]>(`/api/patients/${id}/medications${qs({ include_history: history })}`);

export type MedicationInput = {
  medicine: string;
  dose: string;
  route: string;
  frequency: string;
  duration?: string;
  prescriber_name: string;
  prescription_ref?: string;
  source: 'clinician_entered' | 'hospital_pharmacy';
  effective_from: string;
  effective_to?: string;
  attest_verified: boolean;
};

export const addMedication = (id: number, body: MedicationInput) =>
  api<Medication>(`/api/patients/${id}/medications`, { method: 'POST', body, fallback: 'Could not record the prescription' });

export const supersedeMedication = (id: number, medicationId: number, body: MedicationInput) =>
  api<Medication>(`/api/patients/${id}/medications/${medicationId}/supersede`, { method: 'POST', body });

export const stopMedication = (id: number, medicationId: number, effective_to: string) =>
  api<Medication>(`/api/patients/${id}/medications/${medicationId}/stop`, { method: 'POST', body: { effective_to } });

// ---------------------------------------------------------------- scheduling (staff)
export type SchedulingOverview = {
  by_status: Record<string, number>;
  upcoming: number;
  open_slots: number;
  pending_change_requests: number;
};

export const schedulingOverview = () => api<SchedulingOverview>('/api/scheduling/overview');

export const listAppointments = (params: { status?: string; change_requested?: boolean; page?: number; page_size?: number }) =>
  api<Page<Appointment>>(`/api/scheduling/appointments${qs(params)}`);

export const staffSlots = (params: { department?: string; clinician_id?: number; date_from?: string; date_to?: string }) =>
  api<Slot[]>(`/api/scheduling/slots${qs(params)}`);

export const listClinicians = () =>
  api<Array<{ id: number; full_name: string; department: string; specialty: string | null; location: string }>>(
    '/api/scheduling/clinicians');

export const createClinician = (body: { full_name: string; department: string; specialty?: string; location: string }) =>
  api('/api/scheduling/clinicians', { method: 'POST', body, fallback: 'Could not add the clinician' });

export const createSlots = (body: { clinician_id: number; start: string; duration_minutes: number; count: number }) =>
  api<Slot[]>('/api/scheduling/slots', { method: 'POST', body, fallback: 'Could not create slots' });

export const staffBook = (body: { patient_id: number; slot_id: number; reason?: string; idempotency_key?: string }) =>
  api<Appointment>('/api/scheduling/appointments', { method: 'POST', body, fallback: 'Could not book the appointment' });

export const appointmentAction = (id: number, action: 'confirm' | 'cancel' | 'complete') =>
  api<Appointment>(`/api/scheduling/appointments/${id}/${action}`, { method: 'POST' });

export const resolveChange = (id: number, action: 'approve' | 'reject', new_slot_id?: number) =>
  api<Appointment>(`/api/scheduling/appointments/${id}/resolve-change`, { method: 'POST', body: { action, new_slot_id } });

export const createFollowUp = (body: { patient_id: number; instruction: string; due_date?: string }) =>
  api<{ id: number; visible_to_patient: boolean }>('/api/scheduling/follow-ups', { method: 'POST', body });

export const approveFollowUp = (id: number) =>
  api<{ id: number; visible_to_patient: boolean }>(`/api/scheduling/follow-ups/${id}/approve`, { method: 'POST' });

// ---------------------------------------------------------------- patient portal
export const portalMe = () => api<{ full_name: string; preferred_language: string | null; contact_preference: string; timezone: string }>('/api/portal/me');
export const portalDirectory = () =>
  api<{ departments: string[]; locations: string[]; clinicians: Array<{ id: number; name: string; department: string; location: string }> }>(
    '/api/portal/directory');
export const portalSlots = (params: { department?: string; clinician_id?: number; location?: string; date_from?: string; date_to?: string }) =>
  api<Slot[]>(`/api/portal/slots${qs(params)}`);
export const portalBook = (body: { slot_id: number; reason?: string; idempotency_key: string }) =>
  api<Appointment>('/api/portal/appointments', { method: 'POST', body, fallback: 'Could not book that appointment' });
export const portalAppointments = (scope: 'upcoming' | 'past' | 'all') =>
  api<Appointment[]>(`/api/portal/appointments${qs({ scope })}`);
export const portalRequestChange = (id: number, request_type: 'reschedule' | 'cancel', note?: string) =>
  api<Appointment>(`/api/portal/appointments/${id}/request-change`, { method: 'POST', body: { request_type, note } });
export const portalNotifications = () => api<Array<{ id: number; kind: string; body: string; at: string }>>('/api/portal/notifications');
export const portalFollowUps = () => api<Array<{ id: number; instruction: string; due_date: string | null; approved_at: string }>>('/api/portal/follow-ups');
export const portalRequests = () =>
  api<Array<{ id: number; request_type: string; message: string; created_at: string; status: string }>>('/api/portal/requests');
export const portalCreateRequest = (body: { request_type: string; message: string; idempotency_key: string }) =>
  api<{ id: number; status: string }>('/api/portal/requests', { method: 'POST', body, fallback: 'Could not send your request' });

// ---------------------------------------------------------------- administration
export const listRoutingRules = () => api<RoutingRule[]>('/api/routing/rules');
export const saveRoutingRule = (rule: Omit<RoutingRule, 'id'>, id?: number) =>
  api<RoutingRule>(id ? `/api/routing/rules/${id}` : '/api/routing/rules', {
    method: id ? 'PUT' : 'POST', body: rule, fallback: 'Could not save the routing rule',
  });
export const deleteRoutingRule = (id: number) => api(`/api/routing/rules/${id}`, { method: 'DELETE' });
export const getRoutingPolicy = () => api<RoutingPolicy>('/api/routing/policy');
export const saveRoutingPolicy = (body: Partial<Pick<RoutingPolicy, 'sla_minutes' | 'fallback_team' | 'emergency_team' | 'emergency_instruction'>>) =>
  api<RoutingPolicy>('/api/routing/policy', { method: 'PUT', body, fallback: 'Could not save the policy' });

export const listAuditEvents = (params: { patient_id?: number; action?: string; page?: number; page_size?: number }) =>
  api<{ items: AuditEventRow[]; total: number; page: number; page_size: number }>(`/api/audit/events${qs(params)}`);
export const verifyAuditChain = () => api<{ intact: boolean; first_broken_event_id: number | null }>('/api/audit/verify');

// ---------------------------------------------------------------- downloads that need the bearer token
export async function downloadExport(format: 'json' | 'csv', deIdentify: boolean): Promise<void> {
  const res = await apiFetch(`${API_BASE}/api/export/tickets${qs({ format, de_identify: deIdentify || undefined })}`);
  if (!res.ok) throw new Error('Export failed');
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = `carerouter-tasks${deIdentify ? '-deidentified' : ''}.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
