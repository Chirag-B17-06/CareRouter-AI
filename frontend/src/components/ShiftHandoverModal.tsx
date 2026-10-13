import React, { useState, useEffect } from 'react';
import {
  X,
  FileSpreadsheet,
  FileCode,
  Copy,
  Check,
  RefreshCw,
  AlertOctagon,
  Timer,
  ShieldAlert,
  ClipboardCheck,
  Building,
  CheckCircle2,
  Calendar,
  Layers,
  FileText
} from 'lucide-react';
import { ShiftHandoverReport } from '../types';
import { fetchShiftHandoverReport } from '../services/api';
import { downloadExport } from '../services/careApi';

interface ShiftHandoverModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ShiftHandoverModal: React.FC<ShiftHandoverModalProps> = ({
  isOpen,
  onClose
}) => {
  const [report, setReport] = useState<ShiftHandoverReport | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [deIdentify, setDeIdentify] = useState<boolean>(false);

  const loadReport = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchShiftHandoverReport();
      setReport(data);
    } catch (err) {
      setError((err as Error).message || 'Failed to load shift handover report');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadReport();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCopyBriefing = () => {
    if (!report?.handover_briefing_markdown) return;
    navigator.clipboard.writeText(report.handover_briefing_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6 animate-fade-in">
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/90">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <ClipboardCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white">
                  Hospital Shift Handover &amp; Audit Reporting
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40">
                  PHASE 6 AUDIT
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Consolidated clinical operational handover summary &amp; structured hospital data exports
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadReport}
              disabled={isLoading}
              id="refresh-handover-btn"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-50"
              title="Refresh Shift Report"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              id="close-handover-modal-btn"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="overflow-y-auto p-4 sm:p-6 space-y-6 flex-1">
          {isLoading && !report ? (
            <div className="py-20 flex flex-col items-center justify-center space-y-3 text-slate-400">
              <RefreshCw className="w-7 h-7 text-sky-400 animate-spin" />
              <p className="text-xs font-semibold">Generating Real-Time Handover Briefing...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs">
              <strong>Error loading report:</strong> {error}
            </div>
          ) : report ? (
            <>
              {/* Handover Metrics Header */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-[10px] uppercase font-bold text-slate-400">Total in Shift</div>
                  <div className="text-xl font-extrabold text-white mt-1">{report.total_tickets_in_shift}</div>
                  <div className="text-[10px] text-slate-500">Tasks logged</div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-[10px] uppercase font-bold text-sky-400">Active Tasks</div>
                  <div className="text-xl font-extrabold text-sky-300 mt-1">{report.active_tickets}</div>
                  <div className="text-[10px] text-slate-500">Pending resolution</div>
                </div>

                <div className={`p-3.5 rounded-xl border ${
                  report.stat_emergency_count > 0
                    ? 'bg-red-950/40 border-red-500/50 text-red-200'
                    : 'bg-slate-950 border-slate-800'
                }`}>
                  <div className="text-[10px] uppercase font-bold text-red-400 flex items-center gap-1">
                    <AlertOctagon className="w-3 h-3 text-red-400" />
                    STAT Emergencies
                  </div>
                  <div className="text-xl font-extrabold text-red-300 mt-1">{report.stat_emergency_count}</div>
                  <div className="text-[10px] text-red-400/80">Immediate attention</div>
                </div>

                <div className={`p-3.5 rounded-xl border ${
                  report.overdue_tickets_count > 0
                    ? 'bg-rose-950/40 border-rose-500/50 text-rose-200'
                    : 'bg-slate-950 border-slate-800'
                }`}>
                  <div className="text-[10px] uppercase font-bold text-rose-400 flex items-center gap-1">
                    <Timer className="w-3 h-3 text-rose-400" />
                    Overdue SLA
                  </div>
                  <div className="text-xl font-extrabold text-rose-300 mt-1">{report.overdue_tickets_count}</div>
                  <div className="text-[10px] text-rose-400/80">Breached deadlines</div>
                </div>

                <div className={`p-3.5 rounded-xl border ${
                  report.unreviewed_flagged_count > 0
                    ? 'bg-amber-950/40 border-amber-500/50 text-amber-200'
                    : 'bg-slate-950 border-slate-800'
                }`}>
                  <div className="text-[10px] uppercase font-bold text-amber-400 flex items-center gap-1">
                    <ShieldAlert className="w-3 h-3 text-amber-400" />
                    Needs Review
                  </div>
                  <div className="text-xl font-extrabold text-amber-300 mt-1">{report.unreviewed_flagged_count}</div>
                  <div className="text-[10px] text-amber-400/80">Clinical audit queue</div>
                </div>
              </div>

              {/* Critical Alerts Callout */}
              {report.critical_alerts && report.critical_alerts.length > 0 && (
                <div className="p-4 rounded-xl bg-red-950/30 border border-red-500/40 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-red-300 uppercase tracking-wide">
                    <AlertOctagon className="w-4 h-4 text-red-400" />
                    <span>Urgent Handover Attention Items ({report.critical_alerts.length})</span>
                  </div>
                  <div className="space-y-1.5">
                    {report.critical_alerts.map((alert, idx) => (
                      <div
                        key={idx}
                        className="text-xs p-2 rounded-lg bg-red-950/60 border border-red-800/60 text-red-100 flex items-start gap-2"
                      >
                        <span className="text-red-400 font-bold shrink-0">&bull;</span>
                        <div className="leading-snug">
                          <strong className="text-red-300">Room {alert.room} ({alert.patient}):</strong> {alert.title} — <span className="text-red-400 font-mono text-[10px] uppercase font-bold">{alert.type.replace(/_/g, ' ')}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Department Handover Breakdown Table */}
              <div>
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                  <Building className="w-3.5 h-3.5 text-purple-400" />
                  Department Workload &amp; Accountability Handover
                </h3>
                <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px] font-bold border-b border-slate-800">
                      <tr>
                        <th className="py-2.5 px-3">Department</th>
                        <th className="py-2.5 px-3 text-center">Active Tasks</th>
                        <th className="py-2.5 px-3 text-center">Resolved</th>
                        <th className="py-2.5 px-3 text-center">Overdue SLA</th>
                        <th className="py-2.5 px-3 text-center">STAT Emergencies</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/80">
                      {report.departments.map((dept, i) => (
                        <tr key={i} className="hover:bg-slate-900/40 transition-colors">
                          <td className="py-2 px-3 font-semibold text-slate-200">
                            {dept.department}
                          </td>
                          <td className="py-2 px-3 text-center font-bold text-sky-400">
                            {dept.active_tickets}
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span className="text-emerald-400 font-medium">{dept.resolved_tickets}</span>
                          </td>
                          <td className="py-2 px-3 text-center">
                            {dept.overdue_tickets > 0 ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-300 border border-red-500/40 animate-pulse">
                                {dept.overdue_tickets}
                              </span>
                            ) : (
                              <span className="text-slate-600">0</span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-center">
                            {dept.stat_emergency_tickets > 0 ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-red-600 text-white">
                                {dept.stat_emergency_tickets}
                              </span>
                            ) : (
                              <span className="text-slate-600">0</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Clinical Handover Briefing (Markdown Preview & Copy) */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-sky-400" />
                    Formal Shift Handover Briefing (Markdown)
                  </h3>
                  <button
                    onClick={handleCopyBriefing}
                    id="copy-handover-briefing-btn"
                    className="px-2.5 py-1 rounded-lg bg-sky-600/20 hover:bg-sky-600/30 border border-sky-500/40 text-sky-300 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-300">Copied to Clipboard!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy Briefing</span>
                      </>
                    )}
                  </button>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 max-h-56 overflow-y-auto font-mono text-[11px] text-slate-300 whitespace-pre-wrap leading-relaxed select-all">
                  {report.handover_briefing_markdown}
                </div>
              </div>

              {/* Structured Hospital Data Export Center */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                      <span>Export Hospital Incident &amp; Task Audit Data</span>
                      {deIdentify && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                          HIPAA / DISHA DE-IDENTIFIED
                        </span>
                      )}
                    </h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Download full shift records with audit logs, SLA timings, and clinical notes for hospital EHR or audit compliance.
                    </p>
                  </div>

                  {/* HIPAA De-identification toggle */}
                  <label className="flex items-center gap-2 text-xs font-semibold text-slate-300 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800 cursor-pointer hover:border-slate-700 transition-colors shrink-0">
                    <input
                      type="checkbox"
                      checked={deIdentify}
                      onChange={(e) => setDeIdentify(e.target.checked)}
                      className="rounded bg-slate-950 border-slate-700 text-emerald-500 focus:ring-0 cursor-pointer"
                    />
                    <span className="text-[11px]">De-identify PII (Redact Names &amp; Rooms)</span>
                  </label>
                </div>

                <div className="flex flex-wrap items-center gap-3 pt-1">
                  <button
                    type="button"
                    onClick={() => downloadExport('csv', deIdentify).catch((e) => alert(e.message))}
                    id="export-tickets-csv-btn"
                    className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-md shadow-emerald-600/20 flex items-center gap-2 transition-all"
                  >
                    <FileSpreadsheet className="w-4 h-4" />
                    <span>{deIdentify ? "Export De-Identified CSV (Safe Excel / EHR)" : "Export CSV Spreadsheet (Excel / EHR)"}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => downloadExport('json', deIdentify).catch((e) => alert(e.message))}
                    id="export-tickets-json-btn"
                    className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs shadow-md shadow-sky-600/20 flex items-center gap-2 transition-all"
                  >
                    <FileCode className="w-4 h-4" />
                    <span>{deIdentify ? "Export De-Identified JSON (Research / API)" : "Export Full JSON (FHIR / API Audit)"}</span>
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-between">
          <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>Generated: {report ? new Date(report.generated_at).toLocaleString() : ''}</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors"
          >
            Close View
          </button>
        </div>

      </div>
    </div>
  );
};
