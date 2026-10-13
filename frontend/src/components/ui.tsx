// Small shared building blocks for the coordination views (same slate/sky look as the dashboard).
import React from 'react';
import { AlertTriangle, CheckCircle2, Info, Loader2 } from 'lucide-react';

export const inputCls =
  'w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white placeholder-slate-600 ' +
  'focus:outline-none focus:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/40 disabled:opacity-50';

export const btnPrimary =
  'px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus-visible:ring-2 focus-visible:ring-sky-300';

export const btnSecondary =
  'px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold text-xs ' +
  'flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors';

export const btnDanger =
  'px-3 py-1.5 rounded-lg bg-rose-700/80 hover:bg-rose-600 border border-rose-500/50 text-white font-semibold text-xs ' +
  'flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors';

export const Card: React.FC<{ title?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string }> = ({
  title, actions, children, className = '',
}) => (
  <section className={`rounded-2xl bg-slate-900/70 border border-slate-800 shadow-lg ${className}`}>
    {(title || actions) && (
      <header className="px-4 sm:px-5 pt-4 pb-2 flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">{title}</h3>
        {actions}
      </header>
    )}
    <div className="px-4 sm:px-5 pb-4 pt-2">{children}</div>
  </section>
);

export const Field: React.FC<{ label: string; htmlFor: string; hint?: string; children: React.ReactNode }> = ({
  label, htmlFor, hint, children,
}) => (
  <div>
    <label htmlFor={htmlFor} className="text-[11px] font-medium text-slate-400 block mb-1">{label}</label>
    {children}
    {hint && <p className="text-[10px] text-slate-500 mt-1">{hint}</p>}
  </div>
);

export const Spinner: React.FC<{ label?: string }> = ({ label = 'Loading…' }) => (
  <div role="status" className="py-8 flex items-center justify-center gap-2 text-xs text-slate-400">
    <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
    <span>{label}</span>
  </div>
);

export const EmptyState: React.FC<{ title: string; hint?: string; action?: React.ReactNode }> = ({ title, hint, action }) => (
  <div className="py-10 text-center space-y-2">
    <p className="text-sm font-semibold text-slate-300">{title}</p>
    {hint && <p className="text-xs text-slate-500 max-w-md mx-auto">{hint}</p>}
    {action}
  </div>
);

type BannerKind = 'error' | 'success' | 'info' | 'warning';
const bannerStyles: Record<BannerKind, string> = {
  error: 'bg-rose-950/60 border-rose-500/40 text-rose-200',
  success: 'bg-emerald-950/60 border-emerald-500/40 text-emerald-200',
  info: 'bg-sky-950/50 border-sky-500/30 text-sky-200',
  warning: 'bg-amber-950/50 border-amber-500/40 text-amber-200',
};

export const Banner: React.FC<{ kind: BannerKind; children: React.ReactNode; onRetry?: () => void; onDismiss?: () => void }> = ({
  kind, children, onRetry, onDismiss,
}) => {
  const Icon = kind === 'success' ? CheckCircle2 : kind === 'info' ? Info : AlertTriangle;
  return (
    <div
      role={kind === 'error' || kind === 'warning' ? 'alert' : 'status'}
      className={`p-3 rounded-xl border text-xs flex items-start gap-2 ${bannerStyles[kind]}`}
    >
      <Icon className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
      <div className="flex-1 leading-relaxed">{children}</div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="px-2 py-1 rounded-lg bg-white/10 hover:bg-white/20 font-semibold shrink-0">
          Retry
        </button>
      )}
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label="Dismiss" className="px-1.5 hover:text-white shrink-0">
          &times;
        </button>
      )}
    </div>
  );
};

export const Badge: React.FC<{ tone?: 'sky' | 'emerald' | 'amber' | 'rose' | 'slate' | 'violet'; children: React.ReactNode }> = ({
  tone = 'slate', children,
}) => {
  const tones: Record<string, string> = {
    sky: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    emerald: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    rose: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    violet: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    slate: 'bg-slate-800 text-slate-300 border-slate-700',
  };
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border whitespace-nowrap ${tones[tone]}`}>{children}</span>;
};

export const Pager: React.FC<{ page: number; pageSize: number; total: number; onPage: (p: number) => void }> = ({
  page, pageSize, total, onPage,
}) => {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-2 pt-3 text-xs text-slate-400">
      <span>
        Page {page} of {pages} &middot; {total} total
      </span>
      <span className="flex gap-2">
        <button type="button" className={btnSecondary} disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <button type="button" className={btnSecondary} disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </span>
    </nav>
  );
};

/** Short, friendly local date/time for hospital-timezone ISO strings returned by the API. */
export function formatLocal(iso: string | null | undefined): string {
  if (!iso) return '—';
  // The API already includes the hospital offset (e.g. +05:30); show the wall-clock time it encodes.
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!m) return iso;
  const [, y, mo, d, h, mi] = m;
  const date = new Date(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi));
  return date.toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(/Z|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + 'Z');
  return isNaN(d.getTime()) ? iso : d.toLocaleString();
}

/** Use `useAsync` to get loading/error/retry handling without repeating it in every view. */
export function useAsync<T>(fn: () => Promise<T>, deps: React.DependencyList) {
  const [state, setState] = React.useState<{ data: T | null; loading: boolean; error: string | null }>({
    data: null, loading: true, error: null,
  });
  const [tick, setTick] = React.useState(0);
  React.useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch((e: Error) => alive && setState({ data: null, loading: false, error: e.message || 'Something went wrong' }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}
