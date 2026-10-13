import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, CalendarDays, Bell, LifeBuoy, LogOut, ShieldAlert } from 'lucide-react';
import { Appointment, SessionUser, Slot } from '../types';
import {
  portalAppointments, portalBook, portalCreateRequest, portalDirectory, portalFollowUps, portalMe,
  portalNotifications, portalRequestChange, portalRequests, portalSlots,
} from '../services/careApi';
import { Badge, Banner, Card, EmptyState, Field, Spinner, btnPrimary, btnSecondary, formatDateTime, formatLocal, inputCls, useAsync } from './ui';

interface PatientPortalProps {
  user: SessionUser;
  onLogout: () => void;
}

type PortalTab = 'appointments' | 'requests' | 'updates';

const STATUS_TONE: Record<string, 'emerald' | 'amber' | 'rose' | 'sky' | 'slate'> = {
  confirmed: 'emerald', pending: 'amber', requested: 'amber', cancelled: 'rose', completed: 'sky',
};
const STATUS_LABEL: Record<string, string> = {
  confirmed: 'Confirmed', pending: 'Awaiting confirmation', requested: 'Requested', cancelled: 'Cancelled', completed: 'Completed',
};

const newKey = () => (crypto.randomUUID ? crypto.randomUUID() : `k${Date.now()}${Math.random().toString(16).slice(2)}`);

export const PatientPortal: React.FC<PatientPortalProps> = ({ user, onLogout }) => {
  const [tab, setTab] = useState<PortalTab>('appointments');
  const me = useAsync(portalMe, []);

  const tabs: Array<{ id: PortalTab; label: string; icon: React.ReactNode }> = [
    { id: 'appointments', label: 'Appointments', icon: <CalendarDays className="w-4 h-4" /> },
    { id: 'requests', label: 'Requests', icon: <LifeBuoy className="w-4 h-4" /> },
    { id: 'updates', label: 'Updates', icon: <Bell className="w-4 h-4" /> },
  ];

  return (
    <div className="min-h-screen bg-[#060b13] text-slate-100">
      <header className="border-b border-slate-800 bg-[#060b13]/95 sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 h-16 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-sky-500 to-teal-400 p-0.5">
              <div className="h-full w-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Activity className="h-4 w-4 text-sky-400" aria-hidden="true" />
              </div>
            </div>
            <div className="leading-tight">
              <h1 className="text-base font-bold">CareRouter <span className="text-sky-400">AI</span> · Patient portal</h1>
              <p className="text-[11px] text-slate-400">Signed in as {me.data?.full_name ?? user.full_name}</p>
            </div>
          </div>
          <button type="button" onClick={onLogout} className={btnSecondary}>
            <LogOut className="w-3.5 h-3.5" aria-hidden="true" /> Sign out
          </button>
        </div>
        <nav aria-label="Portal sections" className="max-w-4xl mx-auto px-4 pb-2 flex gap-1 overflow-x-auto">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? 'page' : undefined}
              className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 whitespace-nowrap ${
                tab === t.id ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-900'
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-5">
        <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/30 text-xs text-rose-200 flex items-start gap-2">
          <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span>
            <strong>This portal is not for emergencies.</strong> If you or someone else needs urgent medical help, call your local
            emergency number or go to the nearest emergency department. Requests here are handled during working hours.
          </span>
        </div>
        {me.error && <Banner kind="error" onRetry={me.reload}>{me.error}</Banner>}
        {tab === 'appointments' && <AppointmentsTab timezone={me.data?.timezone} />}
        {tab === 'requests' && <RequestsTab />}
        {tab === 'updates' && <UpdatesTab />}
      </main>
    </div>
  );
};

// ---------------------------------------------------------------- appointments
const AppointmentsTab: React.FC<{ timezone?: string }> = ({ timezone }) => {
  const [scope, setScope] = useState<'upcoming' | 'past'>('upcoming');
  const list = useAsync(() => portalAppointments(scope), [scope]);
  const [booking, setBooking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      {message && <Banner kind="success" onDismiss={() => setMessage(null)}>{message}</Banner>}

      <Card
        title="Your appointments"
        actions={
          <div className="flex gap-2">
            <div role="tablist" aria-label="Appointment period" className="flex rounded-lg overflow-hidden border border-slate-700">
              {(['upcoming', 'past'] as const).map((s) => (
                <button
                  key={s}
                  role="tab"
                  aria-selected={scope === s}
                  type="button"
                  onClick={() => setScope(s)}
                  className={`px-3 py-1.5 text-xs font-semibold capitalize ${scope === s ? 'bg-sky-600 text-white' : 'bg-slate-900 text-slate-400'}`}
                >
                  {s}
                </button>
              ))}
            </div>
            <button type="button" className={btnPrimary} onClick={() => setBooking((b) => !b)} aria-expanded={booking}>
              {booking ? 'Close booking' : 'Book an appointment'}
            </button>
          </div>
        }
      >
        {list.loading && <Spinner label="Loading your appointments…" />}
        {list.error && <Banner kind="error" onRetry={list.reload}>{list.error}</Banner>}
        {!list.loading && !list.error && list.data?.length === 0 && (
          <EmptyState
            title={scope === 'upcoming' ? 'No upcoming appointments' : 'No past appointments'}
            hint={scope === 'upcoming' ? 'Choose “Book an appointment” to see the times that are currently available.' : undefined}
          />
        )}
        <ul className="space-y-3">
          {list.data?.map((a) => (
            <AppointmentRow key={a.id} appt={a} onChanged={(m) => { setMessage(m); list.reload(); }} />
          ))}
        </ul>
        {timezone && <p className="text-[10px] text-slate-500 pt-3">All times are shown in the hospital&apos;s time zone ({timezone}).</p>}
      </Card>

      {booking && (
        <BookingPanel
          onBooked={(a) => {
            setBooking(false);
            setScope('upcoming');
            setMessage(`Your appointment with ${a.slot?.clinician_name ?? 'the clinic'} on ${formatLocal(a.slot?.start_local)} is ${a.status === 'confirmed' ? 'confirmed' : 'received and awaiting confirmation'}.`);
            list.reload();
          }}
        />
      )}
    </div>
  );
};

const AppointmentRow: React.FC<{ appt: Appointment; onChanged: (message: string) => void }> = ({ appt, onChanged }) => {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<'reschedule' | 'cancel'>('reschedule');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canChange = (appt.status === 'confirmed' || appt.status === 'pending') && !appt.change_request;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await portalRequestChange(appt.id, kind, note.trim() || undefined);
      setOpen(false);
      onChanged(`Your ${kind} request was sent. The appointment desk will confirm it.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-white">{formatLocal(appt.slot?.start_local)}</p>
          <p className="text-xs text-slate-400">
            {appt.slot?.clinician_name} &middot; {appt.department} &middot; {appt.slot?.location}
          </p>
          {appt.reason && <p className="text-xs text-slate-500 mt-0.5">Reason: {appt.reason}</p>}
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge tone={STATUS_TONE[appt.status] ?? 'slate'}>{STATUS_LABEL[appt.status] ?? appt.status}</Badge>
          {appt.change_request && <Badge tone="amber">{appt.change_request === 'cancel' ? 'Cancellation' : 'Reschedule'} requested</Badge>}
        </div>
      </div>
      {canChange && !open && (
        <button type="button" className={btnSecondary} onClick={() => setOpen(true)}>Request a change</button>
      )}
      {open && (
        <div className="space-y-2 pt-1">
          <fieldset className="flex gap-4 text-xs text-slate-300">
            <legend className="sr-only">Type of change</legend>
            <label className="flex items-center gap-1.5"><input type="radio" checked={kind === 'reschedule'} onChange={() => setKind('reschedule')} /> Reschedule</label>
            <label className="flex items-center gap-1.5"><input type="radio" checked={kind === 'cancel'} onChange={() => setKind('cancel')} /> Cancel</label>
          </fieldset>
          <label htmlFor={`note-${appt.id}`} className="sr-only">Note for the appointment desk</label>
          <textarea id={`note-${appt.id}`} rows={2} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="Optional note (e.g. preferred time)" className={inputCls} />
          {error && <Banner kind="error">{error}</Banner>}
          <div className="flex gap-2">
            <button type="button" className={btnPrimary} onClick={submit} disabled={busy}>{busy ? 'Sending…' : 'Send request'}</button>
            <button type="button" className={btnSecondary} onClick={() => setOpen(false)} disabled={busy}>Never mind</button>
          </div>
        </div>
      )}
    </li>
  );
};

const BookingPanel: React.FC<{ onBooked: (a: Appointment) => void }> = ({ onBooked }) => {
  const directory = useAsync(portalDirectory, []);
  const [department, setDepartment] = useState('');
  const [clinicianId, setClinicianId] = useState('');
  const [location, setLocation] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const slots = useAsync(
    () => portalSlots({
      department: department || undefined, clinician_id: clinicianId ? Number(clinicianId) : undefined,
      location: location || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined,
    }),
    [department, clinicianId, location, dateFrom, dateTo],
  );
  const [chosen, setChosen] = useState<Slot | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // One idempotency key per attempted slot: a double click or retry can never book twice.
  const keyRef = useRef<{ slot: number; key: string } | null>(null);

  const clinicians = useMemo(
    () => (directory.data?.clinicians ?? []).filter((c) => !department || c.department === department),
    [directory.data, department],
  );

  const confirm = useCallback(async () => {
    if (!chosen) return;
    if (!keyRef.current || keyRef.current.slot !== chosen.id) keyRef.current = { slot: chosen.id, key: newKey() };
    setBusy(true);
    setError(null);
    try {
      onBooked(await portalBook({ slot_id: chosen.id, reason: reason.trim() || undefined, idempotency_key: keyRef.current.key }));
    } catch (e) {
      const err = e as Error & { status?: number };
      setError(err.status === 409 ? `${err.message} The list has been refreshed.` : err.message);
      if (err.status === 409) {
        setChosen(null);
        keyRef.current = null;
        slots.reload();
      }
    } finally {
      setBusy(false);
    }
  }, [chosen, reason, onBooked, slots]);

  useEffect(() => { setChosen(null); }, [department, clinicianId, location, dateFrom, dateTo]);

  return (
    <Card title="Find a time">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <Field label="Department" htmlFor="bk-dept">
          <select id="bk-dept" className={inputCls} value={department} onChange={(e) => { setDepartment(e.target.value); setClinicianId(''); }}>
            <option value="">Any</option>
            {directory.data?.departments.map((d) => <option key={d}>{d}</option>)}
          </select>
        </Field>
        <Field label="Clinician" htmlFor="bk-clin">
          <select id="bk-clin" className={inputCls} value={clinicianId} onChange={(e) => setClinicianId(e.target.value)}>
            <option value="">Any</option>
            {clinicians.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Location" htmlFor="bk-loc">
          <select id="bk-loc" className={inputCls} value={location} onChange={(e) => setLocation(e.target.value)}>
            <option value="">Any</option>
            {directory.data?.locations.map((l) => <option key={l}>{l}</option>)}
          </select>
        </Field>
        <Field label="From" htmlFor="bk-from"><input id="bk-from" type="date" className={inputCls} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></Field>
        <Field label="To" htmlFor="bk-to"><input id="bk-to" type="date" className={inputCls} value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></Field>
      </div>

      <div className="mt-4" aria-live="polite">
        {slots.loading && <Spinner label="Looking for available times…" />}
        {slots.error && <Banner kind="error" onRetry={slots.reload}>{slots.error}</Banner>}
        {!slots.loading && !slots.error && slots.data?.length === 0 && (
          <EmptyState title="No times available" hint="No open appointments match your search. Try a different date range or department, or send a request from the Requests tab." />
        )}
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-80 overflow-y-auto pr-1">
          {slots.data?.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => setChosen(s)}
                aria-pressed={chosen?.id === s.id}
                className={`w-full text-left p-3 rounded-xl border text-xs transition-colors ${
                  chosen?.id === s.id ? 'bg-sky-600/20 border-sky-500' : 'bg-slate-950/70 border-slate-800 hover:border-slate-600'
                }`}
              >
                <span className="block font-semibold text-white">{formatLocal(s.start_local)}</span>
                <span className="block text-slate-400">{s.clinician_name}{s.specialty ? ` · ${s.specialty}` : ''}</span>
                <span className="block text-slate-500">{s.department} · {s.location}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {chosen && (
        <div className="mt-4 p-4 rounded-xl bg-slate-950/80 border border-sky-500/30 space-y-3">
          <p className="text-sm text-white">
            Book <strong>{formatLocal(chosen.start_local)}</strong> with {chosen.clinician_name} ({chosen.location})?
          </p>
          <Field label="Reason for visit (optional)" htmlFor="bk-reason" hint="Please don't include emergency symptoms here.">
            <input id="bk-reason" className={inputCls} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
          </Field>
          {error && <Banner kind="error">{error}</Banner>}
          <div className="flex gap-2">
            <button type="button" className={btnPrimary} onClick={confirm} disabled={busy}>{busy ? 'Booking…' : 'Confirm booking'}</button>
            <button type="button" className={btnSecondary} onClick={() => setChosen(null)} disabled={busy}>Choose another time</button>
          </div>
        </div>
      )}
      {!chosen && error && <div className="mt-3"><Banner kind="error">{error}</Banner></div>}
    </Card>
  );
};

// ---------------------------------------------------------------- requests
const REQUEST_TYPES = [
  ['general', 'General question'], ['billing', 'Billing'], ['insurance', 'Insurance or claims'],
  ['prescription', 'Prescription question'], ['report_followup', 'Test or report follow-up'], ['complaint', 'Feedback or complaint'],
] as const;

const RequestsTab: React.FC = () => {
  const list = useAsync(portalRequests, []);
  const [type, setType] = useState<string>('general');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  const keyRef = useRef<string>(newKey());

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await portalCreateRequest({ request_type: type, message: text.trim(), idempotency_key: keyRef.current });
      setSent('Your request was sent. You can follow its status below.');
      setText('');
      keyRef.current = newKey();
      list.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card title="Send a routine request">
        <form onSubmit={submit} className="space-y-3">
          <Field label="What is this about?" htmlFor="rq-type">
            <select id="rq-type" className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
              {REQUEST_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Your message" htmlFor="rq-msg" hint="Do not use this for emergencies.">
            <textarea id="rq-msg" rows={4} required minLength={3} maxLength={1500} className={inputCls} value={text} onChange={(e) => setText(e.target.value)} />
          </Field>
          {error && <Banner kind="error">{error}</Banner>}
          {sent && <Banner kind="success" onDismiss={() => setSent(null)}>{sent}</Banner>}
          <button type="submit" className={btnPrimary} disabled={busy || text.trim().length < 3}>{busy ? 'Sending…' : 'Send request'}</button>
        </form>
      </Card>
      <Card title="Your requests">
        {list.loading && <Spinner />}
        {list.error && <Banner kind="error" onRetry={list.reload}>{list.error}</Banner>}
        {!list.loading && !list.error && list.data?.length === 0 && <EmptyState title="No requests yet" />}
        <ul className="space-y-2">
          {list.data?.map((r) => (
            <li key={r.id} className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-white capitalize">{r.request_type.replace('_', ' ')}</p>
                <p className="text-xs text-slate-400 line-clamp-2">{r.message}</p>
                <p className="text-[10px] text-slate-500 mt-1">{formatDateTime(r.created_at)}</p>
              </div>
              <Badge tone={r.status === 'Completed' ? 'emerald' : r.status.startsWith('We need') ? 'amber' : 'sky'}>{r.status}</Badge>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
};

// ---------------------------------------------------------------- updates
const UpdatesTab: React.FC = () => {
  const notes = useAsync(portalNotifications, []);
  const followUps = useAsync(portalFollowUps, []);
  return (
    <div className="space-y-4">
      <Card title="Follow-up instructions from your care team">
        {followUps.loading && <Spinner />}
        {followUps.error && <Banner kind="error" onRetry={followUps.reload}>{followUps.error}</Banner>}
        {!followUps.loading && !followUps.error && followUps.data?.length === 0 && (
          <EmptyState title="Nothing to show" hint="Instructions appear here once your care team has reviewed and approved them." />
        )}
        <ul className="space-y-2">
          {followUps.data?.map((f) => (
            <li key={f.id} className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 text-xs text-slate-200">
              <p>{f.instruction}</p>
              <p className="text-[10px] text-slate-500 mt-1">Approved {formatDateTime(f.approved_at)}{f.due_date ? ` · due ${f.due_date}` : ''}</p>
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Confirmations and reminders">
        {notes.loading && <Spinner />}
        {notes.error && <Banner kind="error" onRetry={notes.reload}>{notes.error}</Banner>}
        {!notes.loading && !notes.error && notes.data?.length === 0 && <EmptyState title="No messages yet" />}
        <ul className="space-y-2">
          {notes.data?.map((n) => (
            <li key={n.id} className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 text-xs text-slate-200 flex justify-between gap-3">
              <span>{n.body}</span>
              <span className="text-[10px] text-slate-500 shrink-0">{formatDateTime(n.at)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
};
