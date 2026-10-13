import React, { useState } from 'react';
import { Appointment, AppointmentStatus, PatientSummary, SessionUser, Slot } from '../types';
import {
  appointmentAction, createClinician, createSlots, listAppointments, listClinicians, resolveChange, schedulingOverview,
  searchPatients, staffBook, staffSlots,
} from '../services/careApi';
import { hasPermission } from '../services/session';
import { Badge, Banner, Card, EmptyState, Field, Pager, Spinner, btnPrimary, btnSecondary, formatLocal, inputCls, useAsync } from './ui';

const STATUS_TONE: Record<AppointmentStatus, 'emerald' | 'amber' | 'rose' | 'sky' | 'slate'> = {
  requested: 'amber', pending: 'amber', confirmed: 'emerald', cancelled: 'rose', completed: 'sky',
};

export const SchedulingView: React.FC<{ user: SessionUser }> = ({ user }) => {
  const canManage = hasPermission(user, 'appointment:manage');
  const overview = useAsync(schedulingOverview, []);
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [flash, setFlash] = useState<string | null>(null);
  const changes = useAsync(() => listAppointments({ change_requested: true, page_size: 20 }), []);
  const appts = useAsync(() => listAppointments({ status: status || undefined, page, page_size: 15 }), [status, page]);

  const refresh = () => { overview.reload(); changes.reload(); appts.reload(); };

  const act = async (id: number, action: 'confirm' | 'cancel' | 'complete') => {
    try {
      await appointmentAction(id, action);
      setFlash(`Appointment #${id} ${action === 'complete' ? 'completed' : action === 'confirm' ? 'confirmed' : 'cancelled'}.`);
      refresh();
    } catch (e) {
      setFlash((e as Error).message);
    }
  };

  return (
    <div className="space-y-5 animate-fade-in">
      {flash && <Banner kind="info" onDismiss={() => setFlash(null)}>{flash}</Banner>}

      <section aria-label="Appointment overview" className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {overview.loading && <div className="col-span-full"><Spinner /></div>}
        {overview.error && <div className="col-span-full"><Banner kind="error" onRetry={overview.reload}>{overview.error}</Banner></div>}
        {overview.data && (
          <>
            {[
              ['Upcoming', overview.data.upcoming], ['Open slots', overview.data.open_slots],
              ['Confirmed', overview.data.by_status.confirmed ?? 0], ['Pending confirmation', (overview.data.by_status.pending ?? 0) + (overview.data.by_status.requested ?? 0)],
              ['Change requests', overview.data.pending_change_requests],
            ].map(([label, value]) => (
              <div key={label as string} className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{label}</p>
                <p className="text-2xl font-extrabold text-white">{value}</p>
              </div>
            ))}
          </>
        )}
      </section>

      <Card title={`Change requests (${changes.data?.total ?? 0})`}>
        {changes.loading && <Spinner />}
        {changes.error && <Banner kind="error" onRetry={changes.reload}>{changes.error}</Banner>}
        {!changes.loading && changes.data?.items.length === 0 && <EmptyState title="No pending change requests" />}
        <ul className="space-y-2">
          {changes.data?.items.map((a) => (
            <ChangeRequestRow key={a.id} appt={a} canManage={canManage} onDone={(m) => { setFlash(m); refresh(); }} />
          ))}
        </ul>
      </Card>

      <Card
        title="Appointments"
        actions={
          <div>
            <label htmlFor="appt-status" className="sr-only">Filter by status</label>
            <select id="appt-status" className={inputCls} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">All statuses</option>
              {['requested', 'pending', 'confirmed', 'cancelled', 'completed'].map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
        }
      >
        {appts.loading && <Spinner />}
        {appts.error && <Banner kind="error" onRetry={appts.reload}>{appts.error}</Banner>}
        {!appts.loading && appts.data?.items.length === 0 && <EmptyState title="No appointments" hint="Appointments appear here when patients or staff book them." />}
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <caption className="sr-only">Appointments</caption>
            <thead className="text-slate-500 border-b border-slate-800">
              <tr><th className="py-2 pr-3">When</th><th className="pr-3">Clinician</th><th className="pr-3">Department</th><th className="pr-3">Patient</th><th className="pr-3">Status</th><th /></tr>
            </thead>
            <tbody>
              {appts.data?.items.map((a) => (
                <tr key={a.id} className="border-b border-slate-800/60 align-top">
                  <td className="py-2 pr-3 text-slate-200">{formatLocal(a.slot?.start_local)}</td>
                  <td className="pr-3 text-slate-300">{a.slot?.clinician_name}</td>
                  <td className="pr-3 text-slate-400">{a.department}</td>
                  <td className="pr-3 text-slate-500 font-mono">#{a.patient_id}</td>
                  <td className="pr-3"><Badge tone={STATUS_TONE[a.status]}>{a.status}</Badge>{a.change_request && <> <Badge tone="amber">{a.change_request}?</Badge></>}</td>
                  <td className="text-right whitespace-nowrap space-x-1">
                    {canManage && (a.status === 'pending' || a.status === 'requested') && <button type="button" className={btnSecondary} onClick={() => act(a.id, 'confirm')}>Confirm</button>}
                    {canManage && a.status === 'confirmed' && <button type="button" className={btnSecondary} onClick={() => act(a.id, 'complete')}>Complete</button>}
                    {canManage && (a.status === 'pending' || a.status === 'confirmed' || a.status === 'requested') && <button type="button" className={btnSecondary} onClick={() => act(a.id, 'cancel')}>Cancel</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {appts.data && <Pager page={page} pageSize={appts.data.page_size} total={appts.data.total} onPage={setPage} />}
      </Card>

      {canManage && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <BookForPatient onBooked={(m) => { setFlash(m); refresh(); }} />
          <SlotManager onChanged={(m) => { setFlash(m); refresh(); }} />
        </div>
      )}
    </div>
  );
};

const ChangeRequestRow: React.FC<{ appt: Appointment; canManage: boolean; onDone: (m: string) => void }> = ({ appt, canManage, onDone }) => {
  const [newSlot, setNewSlot] = useState('');
  const [error, setError] = useState<string | null>(null);
  const slots = useAsync(
    () => (appt.change_request === 'reschedule' ? staffSlots({ department: appt.department }) : Promise.resolve([] as Slot[])),
    [appt.id],
  );

  const run = async (action: 'approve' | 'reject') => {
    setError(null);
    try {
      await resolveChange(appt.id, action, newSlot ? Number(newSlot) : undefined);
      onDone(`Change request on appointment #${appt.id} ${action === 'approve' ? 'approved' : 'rejected'}.`);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <li className="p-3 rounded-xl bg-slate-950/70 border border-amber-500/30 text-xs space-y-2">
      <div className="flex flex-wrap justify-between gap-2">
        <span className="text-slate-200">
          <strong className="capitalize">{appt.change_request}</strong> requested for {formatLocal(appt.slot?.start_local)} · {appt.slot?.clinician_name} · patient #{appt.patient_id}
        </span>
        <Badge tone="amber">needs action</Badge>
      </div>
      {appt.change_request_note && <p className="text-slate-400">Patient note: {appt.change_request_note}</p>}
      {canManage && (
        <div className="flex flex-wrap items-end gap-2">
          {appt.change_request === 'reschedule' && (
            <div className="min-w-[14rem]">
              <label htmlFor={`ns-${appt.id}`} className="sr-only">New slot</label>
              <select id={`ns-${appt.id}`} className={inputCls} value={newSlot} onChange={(e) => setNewSlot(e.target.value)}>
                <option value="">{slots.loading ? 'Loading slots…' : 'Choose new time…'}</option>
                {slots.data?.map((s) => <option key={s.id} value={s.id}>{formatLocal(s.start_local)} · {s.clinician_name}</option>)}
              </select>
            </div>
          )}
          <button type="button" className={btnPrimary} disabled={appt.change_request === 'reschedule' && !newSlot} onClick={() => run('approve')}>Approve</button>
          <button type="button" className={btnSecondary} onClick={() => run('reject')}>Reject</button>
        </div>
      )}
      {error && <Banner kind="error">{error}</Banner>}
    </li>
  );
};

const BookForPatient: React.FC<{ onBooked: (m: string) => void }> = ({ onBooked }) => {
  const [q, setQ] = useState('');
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [patientId, setPatientId] = useState<number | null>(null);
  const [department, setDepartment] = useState('');
  const clinicians = useAsync(listClinicians, []);
  const departments = Array.from(new Set(clinicians.data?.map((c) => c.department) ?? []));
  const slots = useAsync(() => staffSlots({ department: department || undefined }), [department]);
  const [slotId, setSlotId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const find = async () => {
    setError(null);
    try { setPatients((await searchPatients(q.trim(), 1, 8)).items); } catch (e) { setError((e as Error).message); }
  };

  const book = async () => {
    if (!patientId || !slotId) return;
    setBusy(true);
    setError(null);
    try {
      await staffBook({ patient_id: patientId, slot_id: Number(slotId), idempotency_key: `staff-${patientId}-${slotId}` });
      onBooked('Appointment booked.');
      setSlotId('');
      slots.reload();
    } catch (e) {
      setError((e as Error).message);
      slots.reload();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Book for a patient">
      <div className="space-y-3">
        <div className="flex gap-2 items-end">
          <div className="flex-1"><Field label="Find patient" htmlFor="bp-q"><input id="bp-q" className={inputCls} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, MRN or phone" /></Field></div>
          <button type="button" className={btnSecondary} onClick={find} disabled={q.trim().length < 2}>Search</button>
        </div>
        {patients.length > 0 && (
          <div role="radiogroup" aria-label="Matching patients" className="space-y-1">
            {patients.map((p) => (
              <label key={p.id} className={`flex items-center gap-2 p-2 rounded-lg border text-xs cursor-pointer ${patientId === p.id ? 'border-sky-500 bg-sky-600/10' : 'border-slate-800'}`}>
                <input type="radio" name="bp-patient" checked={patientId === p.id} onChange={() => setPatientId(p.id)} />
                <span className="text-slate-200">{p.full_name}</span>
                <span className="text-slate-500">{p.mrn ? `MRN ${p.mrn}` : p.patient_uid.slice(0, 8)}</span>
              </label>
            ))}
          </div>
        )}
        <Field label="Department" htmlFor="bp-dept">
          <select id="bp-dept" className={inputCls} value={department} onChange={(e) => setDepartment(e.target.value)}>
            <option value="">Any</option>{departments.map((d) => <option key={d}>{d}</option>)}
          </select>
        </Field>
        <Field label="Available time" htmlFor="bp-slot" hint={slots.data?.length === 0 ? 'No open slots. Add some under “Slots and clinicians”.' : undefined}>
          <select id="bp-slot" className={inputCls} value={slotId} onChange={(e) => setSlotId(e.target.value)}>
            <option value="">{slots.loading ? 'Loading…' : 'Choose a time…'}</option>
            {slots.data?.map((s) => <option key={s.id} value={s.id}>{formatLocal(s.start_local)} · {s.clinician_name}</option>)}
          </select>
        </Field>
        {error && <Banner kind="error">{error}</Banner>}
        <button type="button" className={btnPrimary} disabled={busy || !patientId || !slotId} onClick={book}>{busy ? 'Booking…' : 'Book appointment'}</button>
      </div>
    </Card>
  );
};

const SlotManager: React.FC<{ onChanged: (m: string) => void }> = ({ onChanged }) => {
  const clinicians = useAsync(listClinicians, []);
  const [newClin, setNewClin] = useState({ full_name: '', department: '', specialty: '', location: '' });
  const [slot, setSlot] = useState({ clinician_id: '', start: '', duration_minutes: 20, count: 4 });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const addClinician = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await createClinician({ ...newClin, specialty: newClin.specialty || undefined });
      setNewClin({ full_name: '', department: '', specialty: '', location: '' });
      clinicians.reload();
      onChanged('Clinician added.');
    } catch (err) { setError((err as Error).message); }
  };

  const addSlots = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const made = await createSlots({ clinician_id: Number(slot.clinician_id), start: slot.start, duration_minutes: slot.duration_minutes, count: slot.count });
      onChanged(`Created ${made.length} slot(s). Times are in the hospital time zone.`);
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };

  return (
    <Card title="Slots and clinicians">
      <p className="text-[11px] text-slate-500 mb-3">Patients can only book slots created here (or by a scheduling integration). Nothing is generated automatically.</p>
      <form onSubmit={addClinician} className="grid grid-cols-2 gap-2 mb-4">
        <Field label="Clinician name" htmlFor="nc-name"><input id="nc-name" required className={inputCls} value={newClin.full_name} onChange={(e) => setNewClin({ ...newClin, full_name: e.target.value })} /></Field>
        <Field label="Department" htmlFor="nc-dept"><input id="nc-dept" required className={inputCls} value={newClin.department} onChange={(e) => setNewClin({ ...newClin, department: e.target.value })} /></Field>
        <Field label="Specialty" htmlFor="nc-spec"><input id="nc-spec" className={inputCls} value={newClin.specialty} onChange={(e) => setNewClin({ ...newClin, specialty: e.target.value })} /></Field>
        <Field label="Location" htmlFor="nc-loc"><input id="nc-loc" required className={inputCls} value={newClin.location} onChange={(e) => setNewClin({ ...newClin, location: e.target.value })} /></Field>
        <div className="col-span-2"><button type="submit" className={btnSecondary}>Add clinician</button></div>
      </form>
      <form onSubmit={addSlots} className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-800">
        <div className="col-span-2">
          <Field label="Clinician" htmlFor="ns-clin">
            <select id="ns-clin" required className={inputCls} value={slot.clinician_id} onChange={(e) => setSlot({ ...slot, clinician_id: e.target.value })}>
              <option value="">Choose…</option>{clinicians.data?.map((c) => <option key={c.id} value={c.id}>{c.full_name} — {c.department}</option>)}
            </select>
          </Field>
        </div>
        <Field label="First slot starts (hospital time)" htmlFor="ns-start"><input id="ns-start" type="datetime-local" required className={inputCls} value={slot.start} onChange={(e) => setSlot({ ...slot, start: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Minutes each" htmlFor="ns-dur"><input id="ns-dur" type="number" min={5} max={240} className={inputCls} value={slot.duration_minutes} onChange={(e) => setSlot({ ...slot, duration_minutes: Number(e.target.value) })} /></Field>
          <Field label="How many" htmlFor="ns-count"><input id="ns-count" type="number" min={1} max={40} className={inputCls} value={slot.count} onChange={(e) => setSlot({ ...slot, count: Number(e.target.value) })} /></Field>
        </div>
        <div className="col-span-2"><button type="submit" className={btnPrimary} disabled={busy || !slot.clinician_id || !slot.start}>{busy ? 'Creating…' : 'Create slots'}</button></div>
      </form>
      {error && <div className="mt-3"><Banner kind="error">{error}</Banner></div>}
    </Card>
  );
};
