import React, { useState } from 'react';
import {
  X,
  Bed,
  User,
  Clock,
  ShieldAlert,
  Send,
  CheckCircle2,
  AlertTriangle,
  History,
  FileText,
  Building,
  UserCheck,
  Trash2
} from 'lucide-react';
import { Ticket, TicketStatus, AuditLog } from '../types';

interface TicketDetailModalProps {
  ticket: Ticket | null;
  onClose: () => void;
  onUpdateStatus: (ticketId: number, status: TicketStatus) => void;
  onAddNote: (ticketId: number, note: string, author: string) => Promise<void>;
  onDelete?: (ticketId: number) => void;
  fullTranscript?: string;
}

export const TicketDetailModal: React.FC<TicketDetailModalProps> = ({
  ticket,
  onClose,
  onUpdateStatus,
  onAddNote,
  onDelete,
  fullTranscript
}) => {
  const [newNote, setNewNote] = useState<string>('');
  const [author, setAuthor] = useState<string>('Charge Nurse on Duty');
  const [isSubmittingNote, setIsSubmittingNote] = useState<boolean>(false);

  if (!ticket) return null;

  const handleNoteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNote.trim()) return;
    setIsSubmittingNote(true);
    try {
      await onAddNote(ticket.id, newNote, author);
      setNewNote('');
    } catch (err) {
      console.error(err);
      alert('Failed to add note: ' + (err as Error).message);
    } finally {
      setIsSubmittingNote(false);
    }
  };

  const isStat = ticket.urgency === 'STAT_EMERGENCY';

  const getLanguageLabel = (lang?: string) => {
    if (lang === 'kn') return { label: 'ಕನ್ನಡ (Kannada)', class: 'kannada-text bg-purple-500/20 text-purple-300 border-purple-500/40' };
    if (lang === 'hi') return { label: 'हिन्दी (Hindi)', class: 'hindi-text bg-orange-500/20 text-orange-300 border-orange-500/40' };
    return { label: 'English', class: 'bg-sky-500/20 text-sky-300 border-sky-500/40' };
  };

  const langInfo = getLanguageLabel(ticket.language);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6 animate-fade-in">
      <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Modal Header */}
        <div className={`px-6 py-4 border-b flex items-center justify-between ${
          isStat ? 'bg-red-950/60 border-red-500/40' : 'bg-slate-950/80 border-slate-800'
        }`}>
          <div>
            <div className="flex items-center space-x-2">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${
                isStat
                  ? 'bg-red-600 text-white border-red-400 animate-pulse'
                  : 'bg-sky-500/20 text-sky-300 border-sky-500/40'
              }`}>
                {ticket.urgency.replace(/_/g, ' ')}
              </span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${langInfo.class}`}>
                {langInfo.label}
              </span>
              <span className="text-xs text-slate-400">
                Ticket #{ticket.id} &bull; Call Ref #{ticket.call_id || 1}
              </span>
            </div>
            <h2 className="text-base font-bold text-white mt-1">
              {ticket.title}
            </h2>
          </div>
          <button
            onClick={onClose}
            id="close-ticket-detail-btn"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="overflow-y-auto p-4 sm:p-6 space-y-5 flex-1">
          
          {/* Metadata Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Room &amp; Bed</span>
              <span className="text-white font-semibold flex items-center gap-1 mt-0.5">
                <Bed className="w-3.5 h-3.5 text-sky-400" />
                {ticket.room_number}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Patient</span>
              <span className="text-white font-semibold flex items-center gap-1 mt-0.5">
                <User className="w-3.5 h-3.5 text-slate-400" />
                {ticket.patient_name}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Target Department</span>
              <span className="text-sky-300 font-semibold flex items-center gap-1 mt-0.5">
                <Building className="w-3.5 h-3.5 text-sky-400" />
                {ticket.department}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Assigned Role</span>
              <span className="text-slate-300 font-semibold flex items-center gap-1 mt-0.5">
                <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
                {ticket.assigned_to}
              </span>
            </div>
          </div>

          {/* Status Progression Controls */}
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-950/60 border border-slate-800">
            <div>
              <span className="text-[11px] text-slate-400 block font-medium">Task Status</span>
              <span className="text-sm font-bold text-white uppercase mt-0.5 inline-block">
                {ticket.status.replace(/_/g, ' ')}
              </span>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {(['PENDING', 'IN_PROGRESS', 'DISPATCHED', 'RESOLVED'] as TicketStatus[]).map((st) => (
                <button
                  key={st}
                  id={`set-status-${st.toLowerCase()}-btn`}
                  onClick={() => onUpdateStatus(ticket.id, st)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    ticket.status === st
                      ? 'bg-sky-500 text-white shadow-md'
                      : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                  }`}
                >
                  {st.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Extracted Phone Call Context & Quotation */}
          <div>
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-sky-400" />
              Source Voice Context &amp; Decomposed Sentence
            </h4>
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-sm leading-relaxed space-y-2.5">
              <div className={`p-3 rounded-lg bg-sky-950/30 border-l-4 border-sky-400 text-slate-100 text-xs leading-relaxed ${
                ticket.language === 'kn' ? 'kannada-text' : ticket.language === 'hi' ? 'hindi-text' : ''
              }`}>
                &ldquo;{ticket.raw_quote || ticket.description}&rdquo;
              </div>

              {ticket.translated_quote && ticket.language !== 'en' && (
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 text-xs">
                  <span className="text-[10px] uppercase font-bold text-sky-400 block mb-1">
                    English Clinical Translation:
                  </span>
                  &ldquo;{ticket.translated_quote}&rdquo;
                </div>
              )}

              {fullTranscript && (
                <div className="text-xs text-slate-400 mt-2">
                  <span className="font-semibold text-slate-300">Full Ingested Transcript:</span>
                  <p className="mt-1 font-mono text-slate-400 text-[11px] bg-slate-900/60 p-2.5 rounded-lg">
                    {fullTranscript}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Clinical Safety Flags */}
          {ticket.clinical_flags && ticket.clinical_flags.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                Active Clinical Safety Flags
              </h4>
              <div className="flex flex-wrap gap-2">
                {ticket.clinical_flags.map((flag, i) => (
                  <div
                    key={i}
                    className="px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-semibold flex items-center gap-1.5"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                    <span>{flag.replace(/_/g, ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Staff Triage Notes & Add Note */}
          <div>
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-emerald-400" />
              Clinical Triage Notes &amp; Staff Directives
            </h4>
            
            {ticket.triage_notes ? (
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 whitespace-pre-line leading-relaxed font-mono">
                {ticket.triage_notes}
              </div>
            ) : (
              <div className="text-xs text-slate-500 italic p-2">No custom clinical notes recorded yet.</div>
            )}

            {/* Add note form */}
            <form onSubmit={handleNoteSubmit} className="mt-3 flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                placeholder="Staff Role / Name"
                className="w-full sm:w-44 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
              <input
                type="text"
                id="add-ticket-note-input"
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder="Add clinical observation or handoff note..."
                className="flex-1 px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
              <button
                type="submit"
                disabled={isSubmittingNote || !newNote.trim()}
                id="submit-ticket-note-btn"
                className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs shadow-md shadow-sky-600/30 disabled:opacity-50 transition-all flex items-center justify-center gap-1.5 shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Add Note</span>
              </button>
            </form>
          </div>

          {/* Audit Log Timeline */}
          {ticket.audit_logs && ticket.audit_logs.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-purple-400" />
                Audit Trail &amp; Chain of Custody
              </h4>
              <div className="space-y-1.5 p-3 rounded-xl bg-slate-950 border border-slate-800 max-h-40 overflow-y-auto text-xs">
                {ticket.audit_logs.map((log: AuditLog) => (
                  <div key={log.id} className="flex items-start justify-between gap-2 border-b border-slate-900 pb-1.5 last:border-0 last:pb-0">
                    <div>
                      <span className="font-semibold text-slate-300">{log.action}: </span>
                      <span className="text-slate-400">{log.note}</span>
                    </div>
                    <span className="text-[10px] text-slate-500 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-between">
          <div>
            {ticket.status === 'RESOLVED' && onDelete && (
              <button
                onClick={() => {
                  if (window.confirm(`Are you sure you want to permanently delete resolved ticket #${ticket.id} (${ticket.title})?\n\nThis will remove it from the system.`)) {
                    onDelete(ticket.id);
                    onClose();
                  }
                }}
                id="modal-delete-resolved-ticket-btn"
                className="px-3.5 py-1.5 rounded-xl bg-red-950/60 hover:bg-red-900/80 border border-red-500/50 text-red-300 hover:text-white text-xs font-semibold flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5 text-red-400" />
                <span>Delete Resolved Ticket</span>
              </button>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold"
          >
            Close View
          </button>
        </div>

      </div>
    </div>
  );
};
