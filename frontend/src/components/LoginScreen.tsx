import React, { useState } from 'react';
import { Activity, Loader2, LockKeyhole, ShieldCheck } from 'lucide-react';
import { login } from '../services/api';
import { SessionUser } from '../types';

interface LoginScreenProps {
  onSignedIn: (user: SessionUser) => void;
  notice?: string | null;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onSignedIn, notice }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      onSignedIn(await login(username.trim(), password));
    } catch (err) {
      setError((err as Error).message || 'Sign-in failed');
      setPassword('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#060b13] px-4 py-10 text-slate-100">
      <div className="w-full max-w-md space-y-6">
        <div className="flex items-center justify-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-gradient-to-tr from-sky-500 to-teal-400 p-0.5 shadow-lg shadow-sky-500/20">
            <div className="h-full w-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Activity className="h-5 w-5 text-sky-400" aria-hidden="true" />
            </div>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">
            CareRouter <span className="text-sky-400">AI</span>
          </h1>
        </div>

        <form
          onSubmit={submit}
          className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-2xl space-y-4"
          aria-labelledby="login-heading"
        >
          <div className="space-y-1">
            <h2 id="login-heading" className="text-lg font-bold flex items-center gap-2">
              <LockKeyhole className="w-4 h-4 text-sky-400" aria-hidden="true" /> Sign in
            </h2>
            <p className="text-xs text-slate-400">
              Hospital staff and registered patients. Access is limited to your role and every record access is logged.
            </p>
          </div>

          {notice && (
            <div role="status" className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200">
              {notice}
            </div>
          )}

          <div>
            <label htmlFor="login-username" className="text-xs font-medium text-slate-300 block mb-1">
              Username
            </label>
            <input
              id="login-username"
              autoComplete="username"
              autoFocus
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white focus:outline-none focus:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/40"
            />
          </div>
          <div>
            <label htmlFor="login-password" className="text-xs font-medium text-slate-300 block mb-1">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white focus:outline-none focus:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/40"
            />
          </div>

          {error && (
            <div role="alert" className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/40 text-xs text-rose-200">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy || !username || !password}
            className="w-full px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> : <ShieldCheck className="w-4 h-4" aria-hidden="true" />}
            <span>{busy ? 'Signing in…' : 'Sign in'}</span>
          </button>
        </form>

        <p className="text-[11px] text-slate-500 text-center leading-relaxed">
          If this is a medical emergency, do not use this system. Call your local emergency number or the hospital&apos;s emergency line.
        </p>
      </div>
    </div>
  );
};
