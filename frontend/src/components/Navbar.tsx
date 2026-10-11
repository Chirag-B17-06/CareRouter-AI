import React from 'react';
import {
  Activity,
  PhoneCall,
  Volume2,
  VolumeX,
  BarChart3,
  RotateCcw,
  Sparkles,
  Building2,
  Info
} from 'lucide-react';

interface NavbarProps {
  onOpenCallModal: () => void;
  onOpenAnalytics: () => void;
  onOpenInfo: () => void;
  onResetDb: () => void;
  isMuted: boolean;
  onToggleSound: () => void;
  emergencyCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  onOpenCallModal,
  onOpenAnalytics,
  onOpenInfo,
  onResetDb,
  isMuted,
  onToggleSound,
  emergencyCount
}) => {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-[#060b13]/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand & Hospital Unit */}
        <div className="flex items-center space-x-3">
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
                LIVE
              </span>
            </div>
            <p className="text-xs text-slate-400 flex items-center gap-1">
              <Building2 className="w-3 h-3 text-slate-500" />
              St. Jude General &bull; Acute Clinical Dispatch
            </p>
          </div>
        </div>

        {/* Center Pill: Zero-Key Demo Mode Indicator */}
        <div className="hidden md:flex items-center">
          <button
            onClick={onOpenInfo}
            id="demo-mode-badge-btn"
            className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-sky-950/60 border border-sky-500/30 text-sky-300 text-xs font-medium hover:bg-sky-900/50 hover:border-sky-400 transition-colors shadow-sm"
            title="Click to learn about Zero-Key Demo Mode"
          >
            <Sparkles className="w-3.5 h-3.5 text-sky-400" />
            <span>DEMO MODE: Zero-Key Local NLP</span>
            <Info className="w-3 h-3 text-sky-400/80 ml-0.5" />
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
            title={isMuted ? "Audio alerts muted (Click to enable)" : "Emergency telemetry sound active"}
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4 text-sky-400" />}
            <span className="hidden lg:inline text-[11px] font-medium">{isMuted ? 'Muted' : 'Sound ON'}</span>
          </button>

          {/* Reset Demo DB Button */}
          <button
            onClick={onResetDb}
            id="reset-db-btn"
            className="p-2 sm:px-3 sm:py-1.5 rounded-lg border border-slate-800 bg-slate-900/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors flex items-center gap-1.5 text-xs"
            title="Reset Database to 3 Initial Scenarios"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Reset Seed</span>
          </button>

          {/* Analytics Modal Button */}
          <button
            onClick={onOpenAnalytics}
            id="analytics-btn"
            className="p-2 sm:px-3 sm:py-1.5 rounded-lg border border-slate-800 bg-slate-900/80 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors flex items-center gap-1.5 text-xs"
          >
            <BarChart3 className="w-4 h-4 text-teal-400" />
            <span className="hidden sm:inline font-medium">Analytics</span>
          </button>

          {/* New Call Ingestion Trigger */}
          <button
            onClick={onOpenCallModal}
            id="new-call-trigger-btn"
            className="flex items-center space-x-2 px-3.5 py-2 rounded-lg bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-medium text-xs shadow-lg shadow-sky-500/20 active:scale-95 transition-all"
          >
            <PhoneCall className="w-3.5 h-3.5" />
            <span>Process Call</span>
            {emergencyCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-red-600 font-bold animate-pulse text-white">
                {emergencyCount} STAT
              </span>
            )}
          </button>
        </div>

      </div>
    </header>
  );
};
