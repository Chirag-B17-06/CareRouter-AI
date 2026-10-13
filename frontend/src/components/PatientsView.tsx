import React, { useEffect, useState } from 'react';
import { BadgeCheck, Plus, Search, UserRound } from 'lucide-react';
import { ClinicalRecord, Medication, Patient, PatientCandidate, PatientSummary, SessionUser } from '../types';
import {
  addClinical, addMedication, createPatient, getPatient, listClinical, listMedications, MedicationInput, NewPatient,
  patientTimeline, searchPatients, stopMedication, supersedeMedication, verifyPatient,
} from '../services/careApi';
import { hasPermission } from '../services/session';
import { ApiError } from '../services/api';
import { Badge, Banner, Card, EmptyState, Field, Pager, Spinner, btnPrimary, btnSecondary, formatDateTime, inputCls, useAsync } from './ui';

interface PatientsViewProps {
  user: SessionUser;
  onOpenTask?: (taskId: number) => void;
}

export const PatientsView: React.FC<PatientsViewProps> = ({ user, onOpenTask }) => {
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(query.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [query]);

  const results = useAsync(() => searchPatients(debounced, page), [debounced, page]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[22rem_1fr] gap-5 animate-fade-in">
      <Card
        title="Patients"
        actions={hasPermission(user, 'patient:write') && (
          <button type="button" className={btnSecondary} onClick={() => { setCreating(true); setSelectedId(null); }}>
            <Plus className="w-3.5 h-3.5" aria-hidden="true" /> New
          </button>
        )}
      >
        <div className="relative">
          <label htmlFor="patient-search" className="sr-only">Search patients by name, MRN or phone</label>
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input
            id="patient-search"
            className={`${inputCls} pl-8`}
            placeholder="Search name, MRN or phone"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="mt-3" aria-live="polite">
          {results.loading && <Spinner label="Searching…" />}
          {results.error && <Banner kind="error" onRetry={results.reload}>{results.error}</Banner>}
          {!results.loading && !results.error && results.data?.items.length === 0 && (
            <EmptyState title={debounced ? 'No matching patients' : 'No patients yet'} hint={debounced ? 'Check the spelling, or search by MRN.' : 'Create the first patient profile with “New”.'} />
          )}
          <ul className="space-y-1.5">
            {results.data?.items.map((p) => (
              <li key={p.id}>
                <PatientListItem p={p} active={selectedId === p.id} onSelect={() => { setSelectedId(p.id); setCreating(false); }} />
              </li>
            ))}
          </ul>
          {results.data && <Pager page={page} pageSize={results.data.page_size} total={results.data.total} onPage={setPage} />}
        </div>
      </Card>

      <div>
        {creating ? (
          <NewPatientForm
            onCancel={() => setCreating(false)}
            onCreated={(p) => { setCreating(false); setSelectedId(p.id); results.reload(); }}
            onOpenExisting={(id) => { setCreating(false); setSelectedId(id); }}
          />
        ) : selectedId ? (
          <PatientDetail key={selectedId} id={selectedId} user={user} onOpenTask={onOpenTask} />
        ) : (
          <Card><EmptyState title="Select a patient" hint="Overview cards show only the minimum needed to pick the right person. Details open here and every view is logged." /></Card>
        )}
      </div>
    </div>
  );
};

const PatientListItem: React.FC<{ p: PatientSummary; active: boolean; onSelect: () => void }> = ({ p, active, onSelect }) => (
  <button
    type="button"
    onClick={onSelect}
    aria-pressed={active}
    className={`w-full text-left px-3 py-2.5 rounded-xl border transition-colors flex items-center gap-2.5 ${
      active ? 'bg-sky-600/20 border-sky-500' : 'bg-slate-950/70 border-slate-800 hover:border-slate-600'
    }`}
  >
    <UserRound className="w-4 h-4 text-slate-500 shrink-0" aria-hidden="true" />
    <span className="flex-1 min-w-0">
      <span className="block text-xs font-semibold text-white truncate">{p.full_name}</span>
      <span className="block text-[10px] text-slate-500 truncate">{p.mrn ? `MRN ${p.mrn}` : `ID ${p.patient_uid.slice(0, 8)}`}</span>
    </span>
    {p.identity_verified ? <Badge tone="emerald">Verified</Badge> : <Badge tone="amber">Unverified</Badge>}
  </button>
);

// ---------------------------------------------------------------- create
const NewPatientForm: React.FC<{
  onCreated: (p: Patient) => void; onCancel: () => void; onOpenExisting: (id: number) => void;
}> = ({ onCreated, onCancel, onOpenExisting }) => {
  const [form, setForm] = useState<NewPatient>({ full_name: '', contact_preference: 'in_app' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dupes, setDupes] = useState<PatientCandidate[]>([]);
  const set = (k: keyof NewPatient, v: string) => setForm((f) => ({ ...f, [k]: v || undefined }));

  const submit = async (confirm: boolean) => {
    setBusy(true);
    setError(null);
    try {
      onCreated(await createPatient({ ...form, confirm_not_duplicate: confirm }));
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 409 && err.detail && typeof err.detail === 'object' && 'candidates' in (err.detail as object)) {
        setDupes((err.detail as { candidates: PatientCandidate[] }).candidates);
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="New patient profile">
      <form onSubmit={(e) => { e.preventDefault(); void submit(false); }} className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Full name *" htmlFor="np-name"><input id="np-name" required className={inputCls} onChange={(e) => set('full_name', e.target.value)} /></Field>
          <Field label="Hospital MRN" htmlFor="np-mrn"><input id="np-mrn" className={inputCls} onChange={(e) => set('mrn', e.target.value)} /></Field>
          <Field label="Date of birth" htmlFor="np-dob"><input id="np-dob" type="date" className={inputCls} onChange={(e) => set('date_of_birth', e.target.value)} /></Field>
          <Field label="Sex" htmlFor="np-sex">
            <select id="np-sex" className={inputCls} onChange={(e) => set('sex', e.target.value)}>
              <option value="">Not recorded</option><option>female</option><option>male</option><option>other</option>
            </select>
          </Field>
          <Field label="Phone" htmlFor="np-phone"><input id="np-phone" className={inputCls} onChange={(e) => set('phone', e.target.value)} /></Field>
          <Field label="Email" htmlFor="np-email"><input id="np-email" type="email" className={inputCls} onChange={(e) => set('email', e.target.value)} /></Field>
          <Field label="Preferred language" htmlFor="np-lang"><input id="np-lang" className={inputCls} placeholder="e.g. kn, hi, en" onChange={(e) => set('preferred_language', e.target.value)} /></Field>
          <Field label="Contact preference" htmlFor="np-contact">
            <select id="np-contact" className={inputCls} value={form.contact_preference} onChange={(e) => set('contact_preference', e.target.value)}>
              <option value="in_app">In the patient portal</option><option value="sms">SMS</option><option value="email">Email</option><option value="phone">Phone call</option>
            </select>
          </Field>
        </div>
        {error && <Banner kind="error">{error}</Banner>}
        {dupes.length > 0 && (
          <Banner kind="warning">
            <p className="font-semibold mb-1">Similar patients already exist. Please check before creating another profile.</p>
            <ul className="space-y-1">
              {dupes.map((d) => (
                <li key={d.patient_id} className="flex items-center justify-between gap-2">
                  <span>{d.display_name} <span className="opacity-70">(match {Math.round(d.score * 100)}% · {d.signals.join(', ')})</span></span>
                  <button type="button" className={btnSecondary} onClick={() => onOpenExisting(d.patient_id)}>Open</button>
                </li>
              ))}
            </ul>
            <button type="button" className={`${btnSecondary} mt-2`} disabled={busy} onClick={() => void submit(true)}>
              This is a different person — create anyway
            </button>
          </Banner>
        )}
        <div className="flex gap-2">
          <button type="submit" className={btnPrimary} disabled={busy || form.full_name.trim().length < 2}>{busy ? 'Saving…' : 'Create profile'}</button>
          <button type="button" className={btnSecondary} onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </Card>
  );
};

// ---------------------------------------------------------------- detail
type DetailTab = 'overview' | 'activity' | 'clinical' | 'medications';

const PatientDetail: React.FC<{ id: number; user: SessionUser; onOpenTask?: (id: number) => void }> = ({ id, user, onOpenTask }) => {
  const patient = useAsync(() => getPatient(id), [id]);
  const [tab, setTab] = useState<DetailTab>('overview');
  const canClinical = hasPermission(user, 'clinical:read');
  const canMeds = hasPermission(user, 'medication:read');
  const tabs: Array<[DetailTab, string, boolean]> = [
    ['overview', 'Overview', true], ['activity', 'Conversations & tasks', hasPermission(user, 'conversation:read')],
    ['clinical', 'Clinical record', canClinical], ['medications', 'Medications', canMeds],
  ];

  if (patient.loading) return <Card><Spinner label="Opening patient record…" /></Card>;
  if (patient.error || !patient.data) return <Card><Banner kind="error" onRetry={patient.reload}>{patient.error ?? 'Could not load this patient'}</Banner></Card>;
  const p = patient.data;

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-white">{p.full_name}</h2>
            <p className="text-[11px] text-slate-500 font-mono">ID {p.patient_uid}{p.mrn ? ` · MRN ${p.mrn}` : ''}</p>
          </div>
          <div className="flex items-center gap-2">
            {p.identity_verified ? (
              <Badge tone="emerald"><BadgeCheck className="inline w-3 h-3 mr-0.5" aria-hidden="true" />Identity verified</Badge>
            ) : (
              <>
                <Badge tone="amber">Identity not verified</Badge>
                {hasPermission(user, 'patient:verify') && (
                  <button type="button" className={btnSecondary} onClick={async () => { await verifyPatient(p.id); patient.reload(); }}>
                    Verify identity
                  </button>
                )}
              </>
            )}
          </div>
        </div>
        <div role="tablist" aria-label="Patient sections" className="flex gap-1 mt-4 overflow-x-auto">
          {tabs.filter((t) => t[2]).map(([key, label]) => (
            <button key={key} role="tab" aria-selected={tab === key} type="button" onClick={() => setTab(key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap ${tab === key ? 'bg-sky-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>
              {label}
            </button>
          ))}
        </div>
      </Card>

      {tab === 'overview' && (
        <Card title="Profile">
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-xs">
            {[
              ['Date of birth', p.date_of_birth], ['Sex', p.sex], ['Phone', p.phone], ['Email', p.email],
              ['Preferred language', p.preferred_language], ['Contact preference', p.contact_preference.replace('_', ' ')],
              ['Profile created', formatDateTime(p.created_at)],
            ].map(([k, v]) => (
              <div key={k as string} className="flex justify-between gap-3 border-b border-slate-800/70 py-1">
                <dt className="text-slate-500">{k}</dt><dd className="text-slate-200 text-right">{(v as string) || '—'}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}
      {tab === 'activity' && <ActivityTab id={id} onOpenTask={onOpenTask} />}
      {tab === 'clinical' && canClinical && <ClinicalTab id={id} canWrite={hasPermission(user, 'clinical:write')} />}
      {tab === 'medications' && canMeds && <MedicationsTab id={id} canWrite={hasPermission(user, 'medication:write')} />}
    </div>
  );
};

const ActivityTab: React.FC<{ id: number; onOpenTask?: (id: number) => void }> = ({ id, onOpenTask }) => {
  const t = useAsync(() => patientTimeline(id), [id]);
  if (t.loading) return <Card><Spinner /></Card>;
  if (t.error || !t.data) return <Card><Banner kind="error" onRetry={t.reload}>{t.error}</Banner></Card>;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card title="Tasks">
        {t.data.tasks.length === 0 && <EmptyState title="No linked tasks" hint="Tasks appear after a conversation is linked to this patient." />}
        <ul className="space-y-2">
          {t.data.tasks.map((x) => (
            <li key={x.id} className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-xs">
              <button type="button" className="text-left w-full" onClick={() => onOpenTask?.(x.id)}>
                <span className="block font-semibold text-white line-clamp-1">{x.title}</span>
                <span className="text-slate-500">{x.assigned_team} · {x.status.replace(/_/g, ' ')} · {x.urgency.replace(/_/g, ' ')}</span>
              </button>
            </li>
          ))}
        </ul>
      </Card>
      <div className="space-y-4">
        <Card title="Conversations (summaries)">
          {t.data.conversations.length === 0 && <EmptyState title="None linked" />}
          <ul className="space-y-2">
            {t.data.conversations.map((c) => (
              <li key={c.id} className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-xs text-slate-300">
                <span className="block text-[10px] text-slate-500">{formatDateTime(c.created_at)} · {c.language.toUpperCase()}</span>
                {c.summary}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Appointments">
          {t.data.appointments.length === 0 && <EmptyState title="None" />}
          <ul className="space-y-1.5 text-xs text-slate-300">
            {t.data.appointments.map((a) => (
              <li key={a.id} className="flex justify-between"><span>{a.department}</span><Badge tone="sky">{a.status}</Badge></li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
};

const ClinicalTab: React.FC<{ id: number; canWrite: boolean }> = ({ id, canWrite }) => {
  const rec = useAsync(() => listClinical(id), [id]);
  const [type, setType] = useState('allergy');
  const [text, setText] = useState('');
  const [severity, setSeverity] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await addClinical(id, { record_type: type, description: text.trim(), severity: severity || undefined });
      setText('');
      rec.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Clinical record (clinician-entered or imported)">
      {rec.loading && <Spinner />}
      {rec.error && <Banner kind="error" onRetry={rec.reload}>{rec.error}</Banner>}
      {!rec.loading && rec.data?.length === 0 && <EmptyState title="No clinical entries" hint="Nothing is added from conversations automatically." />}
      <ul className="space-y-2">
        {rec.data?.map((r: ClinicalRecord) => (
          <li key={r.id} className={`p-2.5 rounded-lg border text-xs ${r.entered_in_error ? 'opacity-50 line-through border-slate-800' : 'bg-slate-950/70 border-slate-800'}`}>
            <span className="flex items-center gap-2 mb-0.5"><Badge tone={r.record_type === 'allergy' ? 'rose' : 'sky'}>{r.record_type}</Badge>{r.severity && <Badge>{r.severity}</Badge>}
              <span className="text-[10px] text-slate-500">{formatDateTime(r.recorded_at)}</span></span>
            {r.description}
          </li>
        ))}
      </ul>
      {canWrite && (
        <form onSubmit={submit} className="mt-4 pt-4 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-[8rem_1fr_8rem_auto] gap-2 items-end">
          <Field label="Type" htmlFor="cr-type"><select id="cr-type" className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
            <option>allergy</option><option>condition</option><option>history</option><option>note</option></select></Field>
          <Field label="Entry" htmlFor="cr-text"><input id="cr-text" required minLength={2} className={inputCls} value={text} onChange={(e) => setText(e.target.value)} /></Field>
          <Field label="Severity" htmlFor="cr-sev"><input id="cr-sev" className={inputCls} value={severity} onChange={(e) => setSeverity(e.target.value)} /></Field>
          <button type="submit" className={btnPrimary} disabled={busy}>Add</button>
          {error && <div className="sm:col-span-4"><Banner kind="error">{error}</Banner></div>}
        </form>
      )}
    </Card>
  );
};

const emptyMed = (): MedicationInput => ({
  medicine: '', dose: '', route: 'oral', frequency: '', duration: '', prescriber_name: '', source: 'clinician_entered',
  effective_from: new Date().toISOString().slice(0, 10), attest_verified: false,
});

const MedicationsTab: React.FC<{ id: number; canWrite: boolean }> = ({ id, canWrite }) => {
  const [history, setHistory] = useState(false);
  const meds = useAsync(() => listMedications(id, history), [id, history]);
  const [form, setForm] = useState<MedicationInput>(emptyMed());
  const [supersedeOf, setSupersedeOf] = useState<Medication | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof MedicationInput>(k: K, v: MedicationInput[K]) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = { ...form, duration: form.duration || undefined, prescription_ref: form.prescription_ref || undefined };
    try {
      if (supersedeOf) await supersedeMedication(id, supersedeOf.id, body);
      else await addMedication(id, body);
      setForm(emptyMed());
      setSupersedeOf(null);
      meds.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Verified prescriptions"
      actions={<label className="text-[11px] text-slate-400 flex items-center gap-1.5"><input type="checkbox" checked={history} onChange={(e) => setHistory(e.target.checked)} /> Show history</label>}
    >
      <p className="text-[11px] text-slate-500 mb-3">
        Prescriptions are never created from conversations or by AI. A change is recorded as a new entry that replaces the old one, so history is preserved.
      </p>
      {meds.loading && <Spinner />}
      {meds.error && <Banner kind="error" onRetry={meds.reload}>{meds.error}</Banner>}
      {!meds.loading && meds.data?.length === 0 && <EmptyState title="No active prescriptions on record" />}
      <ul className="space-y-2">
        {meds.data?.map((m) => (
          <li key={m.id} className={`p-3 rounded-xl border text-xs ${m.status === 'active' ? 'bg-slate-950/70 border-slate-800' : 'border-slate-800/60 opacity-60'}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-white">{m.medicine} · {m.dose} · {m.route} · {m.frequency}</span>
              <Badge tone={m.status === 'active' ? 'emerald' : 'slate'}>{m.status.replace('_', ' ')}</Badge>
            </div>
            <p className="text-slate-500 mt-0.5">
              {m.duration ? `${m.duration} · ` : ''}from {m.effective_from}{m.effective_to ? ` to ${m.effective_to}` : ''} · prescriber {m.prescriber_name}
              {m.prescription_ref ? ` · ref ${m.prescription_ref}` : ''}
            </p>
            {canWrite && m.status === 'active' && (
              <div className="flex gap-2 mt-2">
                <button type="button" className={btnSecondary} onClick={() => { setSupersedeOf(m); setForm({ ...emptyMed(), medicine: m.medicine, route: m.route, prescriber_name: m.prescriber_name }); }}>Change (supersede)</button>
                <button type="button" className={btnSecondary} onClick={async () => { await stopMedication(id, m.id, new Date().toISOString().slice(0, 10)); meds.reload(); }}>Stop today</button>
              </div>
            )}
          </li>
        ))}
      </ul>

      {canWrite && (
        <form onSubmit={submit} className="mt-4 pt-4 border-t border-slate-800 space-y-3">
          <h4 className="text-xs font-bold text-slate-300">{supersedeOf ? `Replace ${supersedeOf.medicine}` : 'Record a verified prescription'}</h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <Field label="Medicine *" htmlFor="md-name"><input id="md-name" required className={inputCls} value={form.medicine} onChange={(e) => set('medicine', e.target.value)} /></Field>
            <Field label="Dose *" htmlFor="md-dose"><input id="md-dose" required className={inputCls} value={form.dose} onChange={(e) => set('dose', e.target.value)} /></Field>
            <Field label="Route *" htmlFor="md-route"><input id="md-route" required className={inputCls} value={form.route} onChange={(e) => set('route', e.target.value)} /></Field>
            <Field label="Frequency *" htmlFor="md-freq"><input id="md-freq" required className={inputCls} value={form.frequency} onChange={(e) => set('frequency', e.target.value)} /></Field>
            <Field label="Duration" htmlFor="md-dur"><input id="md-dur" className={inputCls} value={form.duration} onChange={(e) => set('duration', e.target.value)} /></Field>
            <Field label="Prescriber *" htmlFor="md-by"><input id="md-by" required className={inputCls} value={form.prescriber_name} onChange={(e) => set('prescriber_name', e.target.value)} /></Field>
            <Field label="Effective from *" htmlFor="md-from"><input id="md-from" type="date" required className={inputCls} value={form.effective_from} onChange={(e) => set('effective_from', e.target.value)} /></Field>
            <Field label="Effective to" htmlFor="md-to"><input id="md-to" type="date" className={inputCls} value={form.effective_to ?? ''} onChange={(e) => set('effective_to', e.target.value || undefined)} /></Field>
            <Field label="Source" htmlFor="md-src"><select id="md-src" className={inputCls} value={form.source} onChange={(e) => set('source', e.target.value as MedicationInput['source'])}>
              <option value="clinician_entered">Clinician entered</option><option value="hospital_pharmacy">Hospital pharmacy system</option></select></Field>
            <Field label="Prescription reference" htmlFor="md-ref"><input id="md-ref" className={inputCls} value={form.prescription_ref ?? ''} onChange={(e) => set('prescription_ref', e.target.value)} /></Field>
          </div>
          <label className="flex items-start gap-2 text-xs text-slate-300">
            <input type="checkbox" className="mt-0.5" checked={form.attest_verified} onChange={(e) => set('attest_verified', e.target.checked)} />
            <span>I confirm these details match the authoritative prescription and I am authorised to record them.</span>
          </label>
          {error && <Banner kind="error">{error}</Banner>}
          <div className="flex gap-2">
            <button type="submit" className={btnPrimary} disabled={busy || !form.attest_verified}>{busy ? 'Saving…' : supersedeOf ? 'Save replacement' : 'Record prescription'}</button>
            {supersedeOf && <button type="button" className={btnSecondary} onClick={() => { setSupersedeOf(null); setForm(emptyMed()); }}>Cancel</button>}
          </div>
        </form>
      )}
    </Card>
  );
};
