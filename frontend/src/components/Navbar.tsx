import React from 'react';
import {
  Activity,
  Mic,
  Volume2,
  VolumeX,
  BarChart3,
  Building2,
  Layers,
  ClipboardCheck,
  Phone,
  Users,
  CalendarDays,
  Settings2,
  LogOut,
} from 'lucide-react';
import { SessionUser } from '../types';
import { hasPermission } from '../services/session';

export type TabId = 'board' | 'calls' | 'record' | 'patients' | 'scheduling' | 'admin' | 'analytics';

interface NavbarProps {
  user: SessionUser;
  activeTab: TabId;
  onSelectTab: (tab: TabId) => void;
  isMuted: boolean;
  onToggleSound: () => void;
  emergencyCount: number;
  unreviewedCount?: number;
  callsCount?: number;
  onOpenShiftHandover: () => void;
  onLogout: () => void;
}

const ROLE_LABELS: Record<string, string> = {
  admin: 'Administrator',
  nurse: 'Nurse',
  clinician: 'Clinician',
  coordinator: 'Coordinator',
  pharmacist: 'Pharmacist',
  patient: 'Patient',
};

export const Navbar: React.FC<NavbarProps> = ({
  user,
  activeTab,
  onSelectTab,
  isMuted,
  onToggleSound,
  emergencyCount,
  unreviewedCount,
  callsCount,
  onOpenShiftHandover,
  onLogout,
}) => {
  const can = (p: string) => hasPermission(user, p);

  const tabs: Array<{ id: TabId; label: string; icon: React.ReactNode; visible: boolean; badge?: number }> = [
    { id: 'board', label: 'Triage Board', icon: <Layers className="w-3.5 h-3.5" />, visible: can('task:read') },
    { id: 'calls', label: 'Conversations', icon: <Phone className="w-3.5 h-3.5 text-sky-400" />, visible: can('conversation:read'), badge: callsCount },
    { id: 'record', label: 'Record / Ingest', icon: <Mic className="w-3.5 h-3.5 text-rose-400" />, visible: can('audio:transcribe') || can('conversation:write') },
    { id: 'patients', label: 'Patients', icon: <Users className="w-3.5 h-3.5 text-emerald-400" />, visible: can('patient:read') },
    { id: 'scheduling', label: 'Appointments', icon: <CalendarDays className="w-3.5 h-3.5 text-amber-400" />, visible: can('appointment:read_all') },
    { id: 'analytics', label: 'Analytics', icon: <BarChart3 className="w-3.5 h-3.5 text-teal-400" />, visible: can('analytics:read') },
    { id: 'admin', label: 'Administration', icon: <Settings2 className="w-3.5 h-3.5 text-violet-400" />, visible: can('routing:admin') || can('audit:read') || can('user:admin') },
  ];
  const visibleTabs = tabs.filter((t) => t.visible);

  const tabButton = (t: (typeof tabs)[number]) => (
    <button
      key={t.id}
      type="button"
      onClick={() => onSelectTab(t.id)}
      id={`nav-tab-${t.id}`}
      aria-current={activeTab === t.id ? 'page' : undefined}
      className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 whitespace-nowrap focus-visible:ring-2 focus-visible:ring-sky-400 ${
        activeTab === t.id ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20' : 'text-slate-400 hover:text-white'
      }`}
    >
      {t.icon}
      <span>{t.label}</span>
      {t.badge !== undefined && t.badge > 0 && (
        <span className="px-1.5 rounded-full text-[9px] bg-slate-800 text-slate-300 font-mono">{t.badge}</span>
      )}
    </button>
  );

  const handoverButton = can('analytics:read') && (
    <button
      type="button"
      onClick={onOpenShiftHandover}
      id="nav-tab-handover"
      className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-900 transition-all flex items-center gap-1.5 whitespace-nowrap"
      title="Shift Handover Report & Data Export"
    >
      <ClipboardCheck className="w-3.5 h-3.5 text-purple-400" />
      <span>Shift Handover</span>
      {unreviewedCount ? (
        <span className="px-1.5 rounded-full text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono font-bold animate-pulse">
          {unreviewedCount}
        </span>
      ) : null}
    </button>
  );

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-[#060b13]/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-3">
        {/* Brand */}
        <button type="button" className="flex items-center space-x-3 text-left" onClick={() => onSelectTab(visibleTabs[0]?.id ?? 'board')}>
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-500 to-teal-400 p-0.5 shadow-lg shadow-sky-500/20 flex items-center justify-center shrink-0">
            <div className="h-full w-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Activity className="h-5 w-5 text-sky-400" />
            </div>
          </div>
          <div className="hidden xl:block">
            <h1 className="text-lg font-bold tracking-tight text-white leading-tight">
              CareRouter <span className="text-sky-400">AI</span>
            </h1>
            <p className="text-xs text-slate-400 flex items-center gap-1">
              <Building2 className="w-3 h-3 text-slate-500" />
              Patient coordination &bull; ಕನ್ನಡ | हिन्दी | English
            </p>
          </div>
        </button>

        {/* Desktop tabs */}
        <nav aria-label="Primary" className="hidden xl:flex items-center p-1 rounded-xl bg-slate-950 border border-slate-800">
          {visibleTabs.map(tabButton)}
          {handoverButton}
        </nav>

        {/* Right controls */}
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={onToggleSound}
            id="toggle-audio-btn"
            className={`p-2 rounded-lg border text-xs transition-colors flex items-center gap-1.5 ${
              isMuted
                ? 'bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300'
                : 'bg-sky-500/10 border-sky-500/30 text-sky-300 hover:bg-sky-500/20'
            }`}
            aria-pressed={!isMuted}
            title={isMuted ? 'Audio alerts muted (click to enable)' : 'Emergency sound alerts active'}
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4 text-sky-400" />}
            <span className="sr-only">{isMuted ? 'Unmute alerts' : 'Mute alerts'}</span>
          </button>

          {emergencyCount > 0 && (
            <span className="px-2 py-1 rounded-lg text-[11px] bg-red-700 font-bold animate-pulse text-white" role="status">
              {emergencyCount} STAT
            </span>
          )}

          <div className="hidden sm:flex flex-col items-end leading-tight pr-1">
            <span className="text-xs font-semibold text-slate-200 max-w-[10rem] truncate">{user.full_name}</span>
            <span className="text-[10px] text-slate-500">
              {ROLE_LABELS[user.role] ?? user.role}
              {user.department ? ` · ${user.department}` : ''}
            </span>
          </div>
          <button
            type="button"
            onClick={onLogout}
            className="p-2 rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:text-white hover:bg-slate-800 flex items-center gap-1.5 text-xs"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden md:inline">Sign out</span>
          </button>
        </div>
      </div>

      {/* Mobile / tablet tabs */}
      <nav aria-label="Primary (compact)" className="xl:hidden border-t border-slate-800/80 overflow-x-auto no-scrollbar">
        <div className="flex items-center gap-1 px-3 py-2 min-w-max">
          {visibleTabs.map(tabButton)}
          {handoverButton}
        </div>
      </nav>
    </header>
  );
};
