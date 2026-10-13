import React, { useState } from 'react';
import { RoutingRule, SessionUser } from '../types';
import {
  deleteRoutingRule, getRoutingPolicy, listAuditEvents, listRoutingRules, saveRoutingPolicy, saveRoutingRule, verifyAuditChain,
} from '../services/careApi';
import { hasPermission } from '../services/session';
import { Badge, Banner, Card, EmptyState, Field, Pager, Spinner, btnDanger, btnPrimary, btnSecondary, formatDateTime, inputCls, useAsync } from './ui';

type Section = 'routing' | 'audit';

export const AdminView: React.FC<{ user: SessionUser }> = ({ user }) => {
  const canRouting = hasPermission(user, 'routing:admin');
  const canAudit = hasPermission(user, 'audit:read');
  const [section, setSection] = useState<Section>(canRouting ? 'routing' : 'audit');

  return (
    <div className="space-y-5 animate-fade-in">
      <div role="tablist" aria-label="Administration" className="flex gap-1">
        {canRouting && <button role="tab" aria-selected={section === 'routing'} type="button" onClick={() => setSection('routing')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold ${section === 'routing' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>Routing &amp; priority policy</button>}
        {canAudit && <button role="tab" aria-selected={section === 'audit'} type="button" onClick={() => setSection('audit')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold ${section === 'audit' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>Audit trail</button>}
      </div>
      {section === 'routing' && canRouting && <RoutingAdmin />}
      {section === 'audit' && canAudit && <AuditAdmin />}
    </div>
  );
};

const blankRule = (): Omit<RoutingRule, 'id'> => ({
  name: '', priority: 100, match_category: null, match_urgency: null, match_keyword: null, target_team: '', is_active: true,
});

const RoutingAdmin: React.FC = () => {
  const rules = useAsync(listRoutingRules, []);
  const policy = useAsync(getRoutingPolicy, []);
  const [editing, setEditing] = useState<{ id?: number; rule: Omit<RoutingRule, 'id'> } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const saveRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    setError(null);
    try {
      await saveRoutingRule(editing.rule, editing.id);
      setEditing(null);
      setFlash('Routing rule saved. It applies to new tasks only.');
      rules.reload();
    } catch (err) { setError((err as Error).message); }
  };

  return (
    <>
      {flash && <Banner kind="success" onDismiss={() => setFlash(null)}>{flash}</Banner>}
      <Card
        title="Routing rules"
        actions={<button type="button" className={btnPrimary} onClick={() => setEditing({ rule: blankRule() })}>Add rule</button>}
      >
        <p className="text-[11px] text-slate-500 mb-3">
          Rules are checked lowest priority number first. If none match, the built-in defaults apply, then the fallback queue.
          Emergencies always go to the emergency team and cannot be diverted by a rule.
        </p>
        {rules.loading && <Spinner />}
        {rules.error && <Banner kind="error" onRetry={rules.reload}>{rules.error}</Banner>}
        {!rules.loading && rules.data?.length === 0 && <EmptyState title="No custom rules" hint="Built-in defaults are in use." />}
        <ul className="space-y-2">
          {rules.data?.map((r) => (
            <li key={r.id} className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 text-xs flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold text-white">{r.priority}. {r.name} {!r.is_active && <Badge>disabled</Badge>}</p>
                <p className="text-slate-500">
                  {[r.match_category && `category ${r.match_category}`, r.match_urgency && `urgency ${r.match_urgency}`, r.match_keyword && `contains “${r.match_keyword}”`].filter(Boolean).join(' · ') || 'matches everything'}
                  {' → '}<span className="text-sky-300">{r.target_team}</span>
                </p>
              </div>
              <div className="flex gap-2">
                <button type="button" className={btnSecondary} onClick={() => setEditing({ id: r.id, rule: { ...r } })}>Edit</button>
                <button type="button" className={btnDanger} onClick={async () => { await deleteRoutingRule(r.id); rules.reload(); }}>Delete</button>
              </div>
            </li>
          ))}
        </ul>

        {editing && (
          <form onSubmit={saveRule} className="mt-4 pt-4 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Rule name" htmlFor="rr-name"><input id="rr-name" required className={inputCls} value={editing.rule.name} onChange={(e) => setEditing({ ...editing, rule: { ...editing.rule, name: e.target.value } })} /></Field>
            <Field label="Priority (lower runs first)" htmlFor="rr-prio"><input id="rr-prio" type="number" min={1} className={inputCls} value={editing.rule.priority} onChange={(e) => setEditing({ ...editing, rule: { ...editing.rule, priority: Number(e.target.value) } })} /></Field>
            <Field label="When category is" htmlFor="rr-cat">
              <select id="rr-cat" className={inputCls} value={editing.rule.match_category ?? ''} onChange={(e) => setEditing({ ...editing, rule: { ...editing.rule, match_category: e.target.value || null } })}>
                <option value="">Any</option>{policy.data?.task_categories.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="When urgency is" htmlFor="rr-urg">
              <select id="rr-urg" className={inputCls} value={editing.rule.match_urgency ?? ''} onChange={(e) => setEditing({ ...editing, rule: { ...editing.rule, match_urgency: e.target.value || null } })}>
                <option value="">Any</option><option>URGENT</option><option>ROUTINE</option><option>INQUIRY</option>
              </select>
            </Field>
            <Field label="When text contains" htmlFor="rr-kw"><input id="rr-kw" className={inputCls} value={editing.rule.match_keyword ?? ''} onChange={(e) => setEditing({ ...editing, rule: { ...editing.rule, match_keyword: e.target.value || null } })} /></Field>
            <Field label="Send to team" htmlFor="rr-team"><input id="rr-team" required className={inputCls} value={editing.rule.target_team} onChange={(e) => setEditing({ ...editing, rule: { ...editing.rule, target_team: e.target.value } })} /></Field>
            <label className="flex items-center gap-2 text-xs text-slate-300 sm:col-span-2">
              <input type="checkbox" checked={editing.rule.is_active} onChange={(e) => setEditing({ ...editing, rule: { ...editing.rule, is_active: e.target.checked } })} /> Rule is active
            </label>
            {error && <div className="sm:col-span-2"><Banner kind="error">{error}</Banner></div>}
            <div className="sm:col-span-2 flex gap-2">
              <button type="submit" className={btnPrimary}>Save rule</button>
              <button type="button" className={btnSecondary} onClick={() => setEditing(null)}>Cancel</button>
            </div>
          </form>
        )}
      </Card>

      <PolicyCard policy={policy} onSaved={() => setFlash('Policy saved.')} />
    </>
  );
};

const PolicyCard: React.FC<{ policy: ReturnType<typeof useAsync<Awaited<ReturnType<typeof getRoutingPolicy>>>>; onSaved: () => void }> = ({ policy, onSaved }) => {
  const [draft, setDraft] = useState<{ sla: Record<string, number>; fallback: string; emergencyTeam: string; instruction: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const data = policy.data;

  React.useEffect(() => {
    if (data) setDraft({ sla: { ...data.sla_minutes }, fallback: data.fallback_team, emergencyTeam: data.emergency_team, instruction: data.emergency_instruction });
  }, [data]);

  if (policy.loading) return <Card title="Priority and escalation policy"><Spinner /></Card>;
  if (policy.error || !data || !draft) return <Card title="Priority and escalation policy"><Banner kind="error" onRetry={policy.reload}>{policy.error ?? 'Not available'}</Banner></Card>;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await saveRoutingPolicy({ sla_minutes: draft.sla, fallback_team: draft.fallback, emergency_team: draft.emergencyTeam, emergency_instruction: draft.instruction });
      onSaved();
      policy.reload();
    } catch (err) { setError((err as Error).message); }
  };

  return (
    <Card title="Priority and escalation policy">
      <form onSubmit={save} className="space-y-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {(['STAT_EMERGENCY', 'URGENT', 'ROUTINE', 'INQUIRY'] as const).map((u) => (
            <Field key={u} label={`${u.replace('_', ' ')} target (min)`} htmlFor={`sla-${u}`}>
              <input id={`sla-${u}`} type="number" min={1} max={u === 'STAT_EMERGENCY' ? 15 : 10080} className={inputCls}
                value={draft.sla[u]} onChange={(e) => setDraft({ ...draft, sla: { ...draft.sla, [u]: Number(e.target.value) } })} />
            </Field>
          ))}
        </div>
        <p className="text-[10px] text-slate-500">Emergency response targets cannot be configured above 15 minutes.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Emergency team" htmlFor="pol-em"><input id="pol-em" className={inputCls} value={draft.emergencyTeam} onChange={(e) => setDraft({ ...draft, emergencyTeam: e.target.value })} /></Field>
          <Field label="Fallback queue (no rule matched)" htmlFor="pol-fb"><input id="pol-fb" className={inputCls} value={draft.fallback} onChange={(e) => setDraft({ ...draft, fallback: e.target.value })} /></Field>
        </div>
        <Field label="Emergency escalation instruction shown on emergency tasks" htmlFor="pol-ins" hint="Describe your hospital's approved emergency procedure. The system never replaces clinical triage.">
          <textarea id="pol-ins" rows={2} className={inputCls} value={draft.instruction} onChange={(e) => setDraft({ ...draft, instruction: e.target.value })} />
        </Field>
        {error && <Banner kind="error">{error}</Banner>}
        <button type="submit" className={btnPrimary}>Save policy</button>
      </form>
    </Card>
  );
};

const AuditAdmin: React.FC = () => {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState('');
  const [patientId, setPatientId] = useState('');
  const events = useAsync(() => listAuditEvents({ page, page_size: 25, action: action || undefined, patient_id: patientId ? Number(patientId) : undefined }), [page, action, patientId]);
  const [chain, setChain] = useState<string | null>(null);

  return (
    <Card
      title="Audit trail"
      actions={
        <button type="button" className={btnSecondary} onClick={async () => {
          const r = await verifyAuditChain();
          setChain(r.intact ? 'Audit chain verified: no events have been altered or removed.' : `Audit chain broken at event #${r.first_broken_event_id}.`);
        }}>Verify integrity</button>
      }
    >
      {chain && <div className="mb-3"><Banner kind={chain.startsWith('Audit chain verified') ? 'success' : 'error'} onDismiss={() => setChain(null)}>{chain}</Banner></div>}
      <div className="grid grid-cols-2 gap-3 max-w-md mb-3">
        <Field label="Action" htmlFor="au-act"><input id="au-act" className={inputCls} placeholder="e.g. patient_viewed" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} /></Field>
        <Field label="Patient id" htmlFor="au-pat"><input id="au-pat" type="number" className={inputCls} value={patientId} onChange={(e) => { setPatientId(e.target.value); setPage(1); }} /></Field>
      </div>
      {events.loading && <Spinner />}
      {events.error && <Banner kind="error" onRetry={events.reload}>{events.error}</Banner>}
      {!events.loading && events.data?.items.length === 0 && <EmptyState title="No events match" />}
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <caption className="sr-only">Audit events</caption>
          <thead className="text-slate-500 border-b border-slate-800"><tr><th className="py-2 pr-3">When</th><th className="pr-3">Who</th><th className="pr-3">Action</th><th className="pr-3">Resource</th><th>Outcome</th></tr></thead>
          <tbody>
            {events.data?.items.map((e) => (
              <tr key={e.id} className="border-b border-slate-800/60">
                <td className="py-1.5 pr-3 text-slate-400 whitespace-nowrap">{formatDateTime(e.occurred_at)}</td>
                <td className="pr-3 text-slate-300">{e.actor_role ?? 'system'}{e.actor_user_id ? ` #${e.actor_user_id}` : ''}</td>
                <td className="pr-3 text-slate-200 font-mono">{e.action}</td>
                <td className="pr-3 text-slate-500">{e.resource_type}{e.resource_id ? ` #${e.resource_id}` : ''}{e.patient_id ? ` · patient #${e.patient_id}` : ''}</td>
                <td><Badge tone={e.outcome === 'success' ? 'emerald' : 'rose'}>{e.outcome}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {events.data && <Pager page={page} pageSize={events.data.page_size} total={events.data.total} onPage={setPage} />}
    </Card>
  );
};
