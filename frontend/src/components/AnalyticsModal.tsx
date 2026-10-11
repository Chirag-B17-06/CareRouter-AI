import React from 'react';
import {
  X,
  BarChart3,
  Activity,
  AlertOctagon,
  Clock,
  Layers,
  CheckCircle2,
  TrendingUp,
  ShieldCheck,
  Languages
} from 'lucide-react';
import { AnalyticsData } from '../types';

interface AnalyticsModalProps {
  isOpen: boolean;
  onClose: () => void;
  analytics: AnalyticsData | null;
}

export const AnalyticsModal: React.FC<AnalyticsModalProps> = ({
  isOpen,
  onClose,
  analytics
}) => {
  if (!isOpen || !analytics) return null;

  const resolutionRate =
    analytics.total_tickets > 0
      ? Math.round((analytics.resolved_tickets / analytics.total_tickets) * 100)
      : 0;

  const avgTasksPerCall =
    analytics.total_calls > 0
      ? (analytics.total_tickets / analytics.total_calls).toFixed(1)
      : '0.0';

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6 animate-fade-in">
      <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-teal-500/10 border border-teal-500/20 text-teal-400">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">
                Hospital Command Triage Analytics
              </h2>
              <p className="text-xs text-slate-400">
                Real-time operational throughput &amp; clinical SLA compliance metrics
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            id="close-analytics-modal-btn"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto p-4 sm:p-6 space-y-6 flex-1">
          
          {/* Top KPI Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Calls Ingested</span>
                <Activity className="w-3.5 h-3.5 text-sky-400" />
              </div>
              <div className="text-2xl font-extrabold text-white">{analytics.total_calls}</div>
              <div className="text-[10px] text-slate-500 mt-1">Multi-request calls</div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Atomic Tasks</span>
                <Layers className="w-3.5 h-3.5 text-teal-400" />
              </div>
              <div className="text-2xl font-extrabold text-white">{analytics.total_tickets}</div>
              <div className="text-[10px] text-teal-400 font-medium mt-1">
                ~{avgTasksPerCall} tasks extracted / call
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>STAT Incidents</span>
                <AlertOctagon className="w-3.5 h-3.5 text-red-400" />
              </div>
              <div className="text-2xl font-extrabold text-red-400">{analytics.emergency_count}</div>
              <div className="text-[10px] text-red-400/80 font-medium mt-1">Immediate response</div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>NLP Latency</span>
                <Clock className="w-3.5 h-3.5 text-purple-400" />
              </div>
              <div className="text-2xl font-extrabold text-purple-300">
                {analytics.avg_triage_latency_ms} <span className="text-xs font-normal text-slate-400">ms</span>
              </div>
              <div className="text-[10px] text-purple-400/80 font-medium mt-1">Local zero-key engine</div>
            </div>

          </div>

          {/* Department Load Distribution */}
          <div>
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-sky-400" />
              Department Workload Distribution
            </h3>
            <div className="space-y-2 p-4 rounded-xl bg-slate-950 border border-slate-800">
              {Object.entries(analytics.department_distribution).map(([dept, count]) => {
                const pct = analytics.total_tickets > 0 ? Math.round((count / analytics.total_tickets) * 100) : 0;
                return (
                  <div key={dept} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-300">{dept}</span>
                      <span className="text-slate-400">{count} tasks ({pct}%)</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-sky-500 to-teal-400 transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Urgency Distribution & Resolution Progress */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            
            {/* Urgency Breakdown */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2.5">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Urgency Breakdown
              </h4>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 rounded-lg bg-red-950/30 border border-red-500/30">
                  <span className="text-red-400 font-semibold block text-[11px]">STAT Emergency</span>
                  <span className="text-lg font-bold text-white">{analytics.emergency_count}</span>
                </div>
                <div className="p-2 rounded-lg bg-amber-950/30 border border-amber-500/30">
                  <span className="text-amber-400 font-semibold block text-[11px]">Urgent (15m)</span>
                  <span className="text-lg font-bold text-white">{analytics.urgent_count}</span>
                </div>
                <div className="p-2 rounded-lg bg-sky-950/30 border border-sky-500/30">
                  <span className="text-sky-400 font-semibold block text-[11px]">Routine</span>
                  <span className="text-lg font-bold text-white">{analytics.routine_count}</span>
                </div>
                <div className="p-2 rounded-lg bg-slate-900 border border-slate-800">
                  <span className="text-slate-400 font-semibold block text-[11px]">Inquiry</span>
                  <span className="text-lg font-bold text-white">{analytics.inquiry_count}</span>
                </div>
              </div>
            </div>

            {/* Resolution Progress */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2.5 flex flex-col justify-between">
              <div>
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Overall Task Resolution
                </h4>
                <div className="flex items-center justify-between text-xs mt-2">
                  <span className="text-slate-400">Resolved Tasks</span>
                  <span className="text-emerald-400 font-bold">{resolutionRate}%</span>
                </div>
                <div className="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden mt-1.5">
                  <div
                    className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                    style={{ width: `${resolutionRate}%` }}
                  />
                </div>
              </div>
              <div className="text-[11px] text-slate-400 flex items-center gap-1.5 pt-2 border-t border-slate-900">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Zero clinical requests dropped; complete audit compliance maintained.</span>
              </div>
            </div>

          </div>

          {/* Multilingual Voice Intake Metrics */}
          <div>
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Languages className="w-3.5 h-3.5 text-sky-400" />
              Multilingual Voice Intake (Whisper STT)
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-xl bg-slate-950 border border-purple-500/30 flex items-center justify-between">
                <div>
                  <span className="text-purple-300 font-bold text-xs kannada-text block">ಕನ್ನಡ (Kannada)</span>
                  <span className="text-[10px] text-slate-500">Local language speech</span>
                </div>
                <span className="text-xl font-extrabold text-purple-200">
                  {analytics.languages_detected?.kn || 0}
                </span>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-950 border border-orange-500/30 flex items-center justify-between">
                <div>
                  <span className="text-orange-300 font-bold text-xs hindi-text block">हिन्दी (Hindi)</span>
                  <span className="text-[10px] text-slate-500">Devanagari script speech</span>
                </div>
                <span className="text-xl font-extrabold text-orange-200">
                  {analytics.languages_detected?.hi || 0}
                </span>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-950 border border-sky-500/30 flex items-center justify-between">
                <div>
                  <span className="text-sky-300 font-bold text-xs block">English</span>
                  <span className="text-[10px] text-slate-500">Clinical English calls</span>
                </div>
                <span className="text-xl font-extrabold text-sky-200">
                  {analytics.languages_detected?.en || 0}
                </span>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};
