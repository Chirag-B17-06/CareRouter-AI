import React from 'react';
import {
  Activity,
  Mic,
  Volume2,
  VolumeX,
  BarChart3,
  Building2,
  Layers,
  ShieldCheck,
  ClipboardCheck,
  Phone
} from 'lucide-react';

interface NavbarProps {
  activeTab: 'board' | 'calls' | 'record' | 'analytics';
  onSelectTab: (tab: 'board' | 'calls' | 'record' | 'analytics') => void;
  isMuted: boolean;
  onToggleSound: () => void;
  emergencyCount: number;
  unreviewedCount?: number;
  callsCount?: number;
  onOpenShiftHandover: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onSelectTab,
  isMuted,
  onToggleSound,
  emergencyCount,
  unreviewedCount,
  callsCount,
  onOpenShiftHandover
}) => {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-[#060b13]/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand & Hospital Unit */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onSelectTab('board')}>
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-500 to-teal-400 p-0.5 shadow-lg shadow-sky-500/20 flex items-center justify-center">
            <div className="h-full w-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Activity className="h-5 w-5 text-sky-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
                CareRouter <span className="text-sky-400">AI</span>
              </h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping mr-1"></span>
                ACTIVE
              </span>
            </div>
            <p className="text-xs text-slate-400 flex items-center gap-1">
              <Building2 className="w-3 h-3 text-slate-500" />
              Multilingual Clinical Dispatch &bull; ಕನ್ನಡ | हिन्दी | English
            </p>
          </div>
        </div>

        {/* Center Navigation Tabs */}
        <div className="hidden md:flex items-center p-1 rounded-xl bg-slate-950 border border-slate-800">
          <button
            onClick={() => onSelectTab('board')}
            id="nav-tab-board"
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'board'
                ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Triage Board</span>
          </button>

          <button
            onClick={() => onSelectTab('calls')}
            id="nav-tab-calls"
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'calls'
                ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Phone className="w-3.5 h-3.5 text-sky-400" />
            <span>Call Transcripts</span>
            {callsCount !== undefined && callsCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[9px] bg-slate-800 text-slate-300 font-mono">
                {callsCount}
              </span>
            )}
          </button>

          <button
            onClick={() => onSelectTab('record')}
            id="nav-tab-record"
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'record'
                ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Mic className="w-3.5 h-3.5 text-rose-400" />
            <span>Record / Ingest Call</span>
          </button>

          <button
            onClick={() => onSelectTab('analytics')}
            id="nav-tab-analytics"
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'analytics'
                ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5 text-teal-400" />
            <span>Analytics</span>
          </button>

          <button
            onClick={onOpenShiftHandover}
            id="nav-tab-handover"
            className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-900 transition-all flex items-center gap-1.5"
            title="Shift Handover Report & Data Export"
          >
            <ClipboardCheck className="w-3.5 h-3.5 text-purple-400" />
            <span>Shift Handover</span>
            {unreviewedCount && unreviewedCount > 0 ? (
              <span className="px-1.5 py-0.2 rounded-full text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono font-bold animate-pulse">
                {unreviewedCount}
              </span>
            ) : null}
          </button>
        </div>

        {/* Right Action Controls */}
        <div className="flex items-center space-x-2 sm:space-x-3">
          {/* Sound Mute Toggle */}
          <button
            onClick={onToggleSound}
            id="toggle-audio-btn"
            className={`p-2 rounded-lg border text-xs transition-colors flex items-center gap-1.5 ${
              isMuted
                ? 'bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300'
                : 'bg-sky-500/10 border-sky-500/30 text-sky-300 hover:bg-sky-500/20'
            }`}
            title={isMuted ? "Audio alerts muted (Click to enable)" : "Emergency sound telemetry active"}
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4 text-sky-400" />}
            <span className="hidden lg:inline text-[11px] font-medium">{isMuted ? 'Muted' : 'Sound ON'}</span>
          </button>

          {/* Quick Record CTA for Mobile */}
          <button
            onClick={() => onSelectTab('record')}
            id="header-record-cta-btn"
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-medium text-xs shadow-lg shadow-red-600/20 active:scale-95 transition-all"
          >
            <Mic className="w-3.5 h-3.5" />
            <span>Record Call</span>
            {emergencyCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-red-700 font-bold animate-pulse text-white">
                {emergencyCount} STAT
              </span>
            )}
          </button>
        </div>

      </div>
    </header>
  );
};
