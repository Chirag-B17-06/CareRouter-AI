import React, { useState } from 'react';
import { ShieldAlert, UserCheck } from 'lucide-react';
import { PatientCandidate, ProcessCallResult } from '../types';
import { confirmPatientLink } from '../services/api';
import { Badge, Banner, btnPrimary, btnSecondary } from './ui';

interface ConversationReviewProps {
  result: ProcessCallResult;
  canLinkPatient: boolean;
  onOpenPatients?: () => void;
}

const ASSERTION_TONE = { reported: 'rose', negated: 'emerald', possible: 'amber' } as const;
const BAND_TONE = { high: 'emerald', medium: 'amber', low: 'slate' } as const;

const Row: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="flex justify-between gap-4 py-1 border-b border-slate-800/60 text-xs">
    <dt className="text-slate-500 shrink-0">{label}</dt>
    <dd className="text-slate-200 text-right">{children}</dd>
  </div>
);

/** Read-only summary of what the system understood, plus the human confirmation step for patient identity. */
export const ConversationReview: React.FC<ConversationReviewProps> = ({ result, canLinkPatient, onOpenPatients }) => {
  const ex = result.structured_extraction;
  const [linkedId, setLinkedId] = useState<number | null>(result.call.patient_match_status === 'confirmed' ? result.call.patient_id ?? null : null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const candidates: PatientCandidate[] = result.patient_match_candidates ?? [];

  const link = async (c: PatientCandidate) => {
    setBusy(c.patient_id);
    setError(null);
    try {
      await confirmPatientLink(result.call.id, c.patient_id);
      setLinkedId(c.patient_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (!ex) return null;
  const val = (v: React.ReactNode) => (v === null || v === undefined || v === '' ? <span className="text-slate-600">not stated</span> : v);

  return (
    <div className="space-y-3 text-xs" aria-label="Structured summary of the conversation">
      {(ex.review_required || result.extraction_warnings?.length) ? (
        <Banner kind="warning">
          <p className="font-semibold flex items-center gap-1.5"><ShieldAlert className="w-3.5 h-3.5" aria-hidden="true" /> Needs human review</p>
          <ul className="list-disc pl-4 mt-1 space-y-0.5">
            {ex.review_reasons.map((r) => <li key={r}>{r}</li>)}
            {result.extraction_warnings?.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </Banner>
      ) : null}

      <dl className="rounded-xl bg-slate-950/70 border border-slate-800 px-3 py-1.5">
        <Row label="Patient name">{val(ex.patient.name)}</Row>
        <Row label="Age / date of birth">{val(ex.patient.age ?? ex.patient.date_of_birth)}</Row>
        <Row label="Patient identifier (as stated)">{val(ex.patient.patient_id)}</Row>
        <Row label="Caller relationship">{val(ex.patient.caller_relationship)}</Row>
        <Row label="Reported concern">{val(ex.reported_concern)}</Row>
        <Row label="Verified diagnosis"><span className="text-slate-500">none — diagnoses are only recorded by clinicians</span></Row>
        <Row label="Overall priority recommendation"><Badge tone={ex.priority === 'emergency' ? 'rose' : ex.priority === 'urgent' ? 'amber' : ex.priority === 'requires_review' ? 'violet' : 'sky'}>{ex.priority.replace('_', ' ')}</Badge></Row>
        {ex.callback.raw_text && <Row label="Callback requested">{ex.callback.requested_date ?? ex.callback.raw_text}</Row>}
        {ex.appointment_intent.intent !== 'none' && <Row label="Appointment intent">{ex.appointment_intent.intent.replace('_', ' ')}</Row>}
      </dl>

      {ex.symptoms.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-400 mb-1">Symptoms mentioned</p>
          <ul className="flex flex-wrap gap-1.5">
            {ex.symptoms.map((s, i) => (
              <li key={i} title={s.evidence ?? undefined}><Badge tone={ASSERTION_TONE[s.assertion]}>{s.assertion === 'negated' ? `no ${s.text}` : s.assertion === 'possible' ? `possible ${s.text}` : s.text}</Badge></li>
            ))}
          </ul>
        </div>
      )}
      {ex.diagnosis_mentions.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-400 mb-1">Diagnoses mentioned (unverified)</p>
          <ul className="flex flex-wrap gap-1.5">
            {ex.diagnosis_mentions.map((d, i) => <li key={i} title={d.evidence ?? undefined}><Badge tone="amber">{d.assertion === 'possible' ? 'possible ' : ''}{d.text}</Badge></li>)}
          </ul>
        </div>
      )}
      {ex.medication_mentions.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-400 mb-1">Medicines mentioned (not a prescription — verify with the prescriber)</p>
          <ul className="flex flex-wrap gap-1.5">{ex.medication_mentions.map((m, i) => <li key={i}><Badge tone="violet">{m.text}</Badge></li>)}</ul>
        </div>
      )}
      {ex.staff_commitments.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-400 mb-1">Commitments made by staff</p>
          <ul className="list-disc pl-4 text-slate-300 space-y-0.5">{ex.staff_commitments.map((c, i) => <li key={i}>{c.commitment}{c.due_text ? ` (${c.due_text})` : ''}</li>)}</ul>
        </div>
      )}
      {ex.uncertainty.length > 0 && (
        <details className="text-slate-400">
          <summary className="cursor-pointer text-[11px] font-semibold">Uncertainty notes ({ex.uncertainty.length})</summary>
          <ul className="list-disc pl-4 mt-1 space-y-0.5">{ex.uncertainty.map((u) => <li key={u}>{u}</li>)}</ul>
        </details>
      )}
      <p className="text-[10px] text-slate-600">
        {ex.confidence === null ? 'No model confidence is available for this extraction. ' : `Model-reported confidence ${Math.round(ex.confidence * 100)}% (not proof of correctness). `}
        Extracted by: {result.call.extraction_provider || 'rules'}.
      </p>

      <div className="rounded-xl bg-slate-950/70 border border-slate-800 p-3 space-y-2">
        <p className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5"><UserCheck className="w-3.5 h-3.5 text-sky-400" aria-hidden="true" /> Patient identity</p>
        {linkedId ? (
          <Banner kind="success">Linked to patient profile #{linkedId}. Tasks from this conversation now appear in that patient&apos;s record.</Banner>
        ) : candidates.length === 0 ? (
          <p className="text-slate-500">
            No existing profile matched what was said. Nothing has been linked.{' '}
            {onOpenPatients && <button type="button" className="text-sky-400 underline" onClick={onOpenPatients}>Search or create a patient</button>}
          </p>
        ) : (
          <>
            <p className="text-slate-500">These profiles may be the same person. Names alone are never enough — confirm only after checking identity.</p>
            <ul className="space-y-1.5">
              {candidates.map((c) => (
                <li key={c.patient_id} className="flex flex-wrap items-center justify-between gap-2 p-2 rounded-lg border border-slate-800">
                  <span className="text-slate-200">
                    {c.display_name}{' '}
                    <Badge tone={BAND_TONE[c.confidence_band]}>{c.confidence_band} confidence</Badge>{' '}
                    <span className="text-slate-500">{c.signals.join(', ')}</span>
                  </span>
                  {canLinkPatient && (
                    <button type="button" className={btnPrimary} disabled={busy !== null} onClick={() => link(c)}>
                      {busy === c.patient_id ? 'Linking…' : 'Confirm this patient'}
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {onOpenPatients && <button type="button" className={btnSecondary} onClick={onOpenPatients}>None of these — search or create</button>}
          </>
        )}
        {error && <Banner kind="error">{error}</Banner>}
      </div>
    </div>
  );
};
