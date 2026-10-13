import React, { useState, useEffect } from 'react';
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
  Trash2,
  CheckCheck,
  Flame,
  Timer,
  Edit3,
  Calendar,
  CreditCard,
  PhoneCall,
  Sparkles,
  Layers,
  ArrowRight
} from 'lucide-react';
import { Ticket, TicketStatus, AuditLog, UrgencyTier, Call, ALL_STATUSES, STATUS_LABELS, isTerminalStatus } from '../types';
import { fetchCall } from '../services/api';

interface TicketDetailModalProps {
  ticket: Ticket | null;
  onClose: () => void;
  onUpdateStatus: (ticketId: number, status: TicketStatus) => void;
  onAddNote: (ticketId: number, note: string, author: string) => Promise<void>;
  onDelete?: (ticketId: number) => void;
  onAcknowledge?: (ticketId: number, staffName: string) => Promise<void>;
  onAssign?: (ticketId: number, staff: string, team: string) => Promise<void>;
  onEscalate?: (ticketId: number, reason: string, staff: string) => Promise<void>;
  onResolve?: (ticketId: number, notes: string, staff: string) => Promise<void>;
  onReview?: (ticketId: number, reviewData: {
    action: 'APPROVE' | 'CORRECT';
    reviewer_name: string;
    review_notes?: string;
    corrected_urgency?: UrgencyTier;
    corrected_department?: string;
    corrected_title?: string;
    corrected_action?: string;
  }) => Promise<void>;
  onSelectSiblingTicket?: (ticket: Ticket) => void;
  fullTranscript?: string;
}

export const TicketDetailModal: React.FC<TicketDetailModalProps> = ({
  ticket,
  onClose,
  onUpdateStatus,
  onAddNote,
  onDelete,
  onAcknowledge,
  onAssign,
  onEscalate,
  onResolve,
  onReview,
  onSelectSiblingTicket,
  fullTranscript
}) => {
  const [newNote, setNewNote] = useState<string>('');
  const [author, setAuthor] = useState<string>('Charge Nurse on Duty');
  const [isSubmittingNote, setIsSubmittingNote] = useState<boolean>(false);

  // Parent Call Record State
  const [parentCall, setParentCall] = useState<Call | null>(null);
  const [isLoadingCall, setIsLoadingCall] = useState<boolean>(false);

  const [ackStaff, setAckStaff] = useState<string>('Nurse on Duty');
  const [assigneeName, setAssigneeName] = useState<string>('');
  const [assignTeam, setAssignTeam] = useState<string>('');
  const [showAssignForm, setShowAssignForm] = useState<boolean>(false);
  const [escalateReason, setEscalateReason] = useState<string>('');
  const [escalateStaff, setEscalateStaff] = useState<string>('Charge Nurse');
  const [showEscalateForm, setShowEscalateForm] = useState<boolean>(false);
  const [resolveNotes, setResolveNotes] = useState<string>('');
  const [resolverName, setResolverName] = useState<string>('Attending Nurse');
  const [showResolveForm, setShowResolveForm] = useState<boolean>(false);
  const [isActionLoading, setIsActionLoading] = useState<boolean>(false);

  // Phase 6: Human Review State
  const [showReviewCorrection, setShowReviewCorrection] = useState<boolean>(false);
  const [reviewerName, setReviewerName] = useState<string>('Clinical Triage Nurse');
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [correctedUrgency, setCorrectedUrgency] = useState<UrgencyTier>(ticket?.urgency || 'ROUTINE');
  const [correctedDept, setCorrectedDept] = useState<string>(ticket?.department || '');
  const [correctedTitle, setCorrectedTitle] = useState<string>(ticket?.title || '');
  const [correctedAction, setCorrectedAction] = useState<string>(ticket?.required_action || '');
  const [isReviewSubmitting, setIsReviewSubmitting] = useState<boolean>(false);

  useEffect(() => {
    if (ticket) {
      setCorrectedUrgency(ticket.urgency);
      setCorrectedDept(ticket.department);
      setCorrectedTitle(ticket.title);
      setCorrectedAction(ticket.required_action || '');
      setShowReviewCorrection(false);
      setReviewNotes('');

      // Fetch parent call if call_id is available
      if (ticket.call_id) {
        setIsLoadingCall(true);
        fetchCall(ticket.call_id)
          .then(setParentCall)
          .catch(() => setParentCall(null))
          .finally(() => setIsLoadingCall(false));
      } else {
        setParentCall(null);
      }
    }
  }, [ticket]);

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

  const handleAckSubmit = async () => {
    if (!onAcknowledge || isActionLoading) return;
    setIsActionLoading(true);
    try {
      await onAcknowledge(ticket.id, ackStaff);
    } catch (err) {
      alert('Failed to acknowledge task: ' + (err as Error).message);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleAssignSubmit = async () => {
    if (!onAssign || isActionLoading) return;
    setIsActionLoading(true);
    try {
      await onAssign(
        ticket.id,
        assigneeName || ticket.assigned_staff || 'Unassigned',
        assignTeam || ticket.assigned_team || ticket.department
      );
      setShowAssignForm(false);
    } catch (err) {
      alert('Failed to reassign task: ' + (err as Error).message);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleEscalateSubmit = async () => {
    if (!onEscalate || !escalateReason.trim() || isActionLoading) return;
    setIsActionLoading(true);
    try {
      await onEscalate(ticket.id, escalateReason, escalateStaff);
      setEscalateReason('');
      setShowEscalateForm(false);
    } catch (err) {
      alert('Failed to escalate task: ' + (err as Error).message);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleResolveSubmit = async () => {
    if (!onResolve || !resolveNotes.trim() || isActionLoading) return;
    setIsActionLoading(true);
    try {
      await onResolve(ticket.id, resolveNotes, resolverName);
      setResolveNotes('');
      setShowResolveForm(false);
    } catch (err) {
      alert('Failed to resolve task: ' + (err as Error).message);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleApproveReview = async () => {
    if (!onReview || !ticket || isReviewSubmitting) return;
    setIsReviewSubmitting(true);
    try {
      await onReview(ticket.id, {
        action: 'APPROVE',
        reviewer_name: reviewerName || 'Clinical Triage Nurse',
        review_notes: reviewNotes || 'Extraction approved as clinically accurate without changes.'
      });
      setShowReviewCorrection(false);
    } catch (err) {
      alert('Failed to approve extraction: ' + (err as Error).message);
    } finally {
      setIsReviewSubmitting(false);
    }
  };

  const handleCorrectReview = async () => {
    if (!onReview || !ticket || isReviewSubmitting) return;
    setIsReviewSubmitting(true);
    try {
      await onReview(ticket.id, {
        action: 'CORRECT',
        reviewer_name: reviewerName || 'Clinical Triage Nurse',
        review_notes: reviewNotes,
        corrected_urgency: correctedUrgency,
        corrected_department: correctedDept,
        corrected_title: correctedTitle,
        corrected_action: correctedAction
      });
      setShowReviewCorrection(false);
    } catch (err) {
      alert('Failed to save clinical correction: ' + (err as Error).message);
    } finally {
      setIsReviewSubmitting(false);
    }
  };

  const isStat = ticket.urgency === 'STAT_EMERGENCY';

  const isAppointmentRequest =
    Boolean(ticket.category && (
      ticket.category.toLowerCase().includes('appointment') ||
      ticket.category.toLowerCase().includes('specialist')
    )) ||
    Boolean(ticket.intent && (
      ticket.intent.includes('appointment') ||
      ticket.intent.includes('specialist')
    ));

  const isBillingOrInsurance =
    Boolean(ticket.category && (
      ticket.category.toLowerCase().includes('billing') ||
      ticket.category.toLowerCase().includes('insurance')
    )) ||
    Boolean(ticket.department && (
      ticket.department.toLowerCase().includes('billing') ||
      ticket.department.toLowerCase().includes('insurance')
    ));

  const isFollowUpCommitment =
    Boolean(ticket.category && (
      ticket.category.toLowerCase().includes('callback') ||
      ticket.category.toLowerCase().includes('follow-up')
    )) ||
    Boolean(ticket.intent && (
      ticket.intent.includes('callback') ||
      ticket.intent.includes('follow_up')
    ));

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
                {STATUS_LABELS[ticket.status] ?? ticket.status.replace(/_/g, ' ')}
              </span>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {ALL_STATUSES.map((st) => (
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
                  {STATUS_LABELS[st]}
                </button>
              ))}
            </div>
          </div>

          {/* Phase 5: Overdue SLA Breach Alert */}
          {ticket.is_overdue && (
            <div className="p-3.5 rounded-xl bg-rose-950/70 border border-rose-500/80 text-rose-200 text-xs flex items-center justify-between gap-3 animate-pulse">
              <div className="flex items-center gap-2">
                <Timer className="w-4 h-4 text-rose-400 shrink-0" />
                <div>
                  <span className="font-extrabold text-rose-300 uppercase tracking-wide block text-[11px]">
                    SLA DEADLINE BREACHED (OVERDUE)
                  </span>
                  <span className="text-[11px] text-rose-200">
                    This clinical request has exceeded its {ticket.sla_minutes || 60}-minute response window. Immediate action or escalation is required.
                  </span>
                </div>
              </div>
              {onEscalate && !ticket.escalation_level && (
                <button
                  onClick={() => setShowEscalateForm(true)}
                  className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shrink-0 shadow-md"
                >
                  Escalate Now
                </button>
              )}
            </div>
          )}

          {/* Phase 6: Human Clinical Review & Audit Correction Panel */}
          {ticket.requires_human_review && !ticket.is_reviewed && (
            <div className="p-4 rounded-xl bg-amber-950/40 border-2 border-amber-500/60 space-y-3 text-xs shadow-lg">
              <div className="flex items-center justify-between border-b border-amber-600/30 pb-2">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                  <span className="font-extrabold text-amber-300 uppercase tracking-wider text-[11px]">
                    Clinical Review Queue &bull; AI Safety Uncertainty Detected
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded text-[9px] font-black uppercase bg-amber-500/20 text-amber-300 border border-amber-500/50">
                  PENDING CLINICAL VALIDATION
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-amber-950/60 border border-amber-700/50 text-[11px] text-amber-200">
                <strong className="text-amber-300 block mb-0.5">Clinical Review Indication:</strong>
                {ticket.human_review_reason || 'Uncertainty or borderline triage urgency detected. Clinical nurse confirmation required.'}
              </div>

              {onReview && (
                <>
                  {!showReviewCorrection ? (
                    <div className="space-y-2.5 pt-1">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <input
                          type="text"
                          value={reviewerName}
                          onChange={(e) => setReviewerName(e.target.value)}
                          placeholder="Reviewer Name / Title (e.g. Charge Nurse Sarah)"
                          className="px-3 py-1.5 rounded-lg bg-slate-900 border border-amber-600/40 text-xs text-white"
                        />
                        <input
                          type="text"
                          value={reviewNotes}
                          onChange={(e) => setReviewNotes(e.target.value)}
                          placeholder="Review notes / verification comment (optional)"
                          className="px-3 py-1.5 rounded-lg bg-slate-900 border border-amber-600/40 text-xs text-white"
                        />
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          onClick={handleApproveReview}
                          disabled={isReviewSubmitting}
                          id="approve-review-btn"
                          className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all disabled:opacity-50 shadow-md shadow-emerald-600/20"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Approve Extraction As-Is</span>
                        </button>

                        <button
                          onClick={() => setShowReviewCorrection(true)}
                          disabled={isReviewSubmitting}
                          id="open-correct-review-btn"
                          className="px-3.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all disabled:opacity-50 shadow-md shadow-amber-600/20"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                          <span>Correct Extraction &amp; Recalculate SLA</span>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="p-3.5 rounded-lg bg-slate-950 border border-amber-500/50 space-y-3">
                      <div className="flex items-center justify-between text-amber-300 font-bold text-xs">
                        <span>Clinical Correction Form (Recomputes SLA &amp; Deadlines)</span>
                        <button
                          onClick={() => setShowReviewCorrection(false)}
                          className="text-slate-400 hover:text-white text-xs"
                        >
                          Cancel
                        </button>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                        <div>
                          <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                            Corrected Urgency Tier
                          </label>
                          <select
                            value={correctedUrgency}
                            onChange={(e) => setCorrectedUrgency(e.target.value as UrgencyTier)}
                            className="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white"
                          >
                            <option value="STAT_EMERGENCY">🚨 STAT EMERGENCY (0m / Immediate)</option>
                            <option value="URGENT">⚠️ URGENT (15m SLA)</option>
                            <option value="ROUTINE">ROUTINE (60m SLA)</option>
                            <option value="INQUIRY">INQUIRY (120m SLA)</option>
                          </select>
                        </div>

                        <div>
                          <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                            Corrected Department
                          </label>
                          <input
                            type="text"
                            value={correctedDept}
                            onChange={(e) => setCorrectedDept(e.target.value)}
                            className="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                          Task Title
                        </label>
                        <input
                          type="text"
                          value={correctedTitle}
                          onChange={(e) => setCorrectedTitle(e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white"
                        />
                      </div>

                      <div>
                        <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                          Required Clinical / Staff Action
                        </label>
                        <textarea
                          value={correctedAction}
                          onChange={(e) => setCorrectedAction(e.target.value)}
                          rows={2}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white resize-none"
                        />
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <input
                          type="text"
                          value={reviewerName}
                          onChange={(e) => setReviewerName(e.target.value)}
                          placeholder="Reviewer Name / Title"
                          className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white"
                        />
                        <input
                          type="text"
                          value={reviewNotes}
                          onChange={(e) => setReviewNotes(e.target.value)}
                          placeholder="Correction notes / rationale"
                          className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white"
                        />
                      </div>

                      <div className="flex items-center gap-2 pt-1">
                        <button
                          onClick={handleCorrectReview}
                          disabled={isReviewSubmitting}
                          id="save-review-correction-btn"
                          className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition-all disabled:opacity-50"
                        >
                          Save Corrections &amp; Recalculate SLA
                        </button>
                        <button
                          onClick={() => setShowReviewCorrection(false)}
                          className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs hover:text-white"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Phase 6: Reviewed & Clinically Verified Status */}
          {ticket.is_reviewed && (
            <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/40 space-y-1.5 text-xs">
              <div className="flex items-center justify-between text-emerald-300 font-bold">
                <span className="flex items-center gap-1.5">
                  <CheckCheck className="w-4 h-4 text-emerald-400" />
                  Clinically Reviewed &amp; Verified
                </span>
                <span className="text-[10px] text-emerald-400 font-mono">
                  {ticket.reviewed_at ? new Date(ticket.reviewed_at).toLocaleString() : ''}
                </span>
              </div>
              <div className="text-slate-300">
                <strong>Reviewed by:</strong> {ticket.reviewed_by || 'Clinical Reviewer'}
              </div>
              {ticket.review_notes && (
                <div className="p-2 rounded bg-slate-950 border border-slate-800 text-[11px] text-emerald-200">
                  {ticket.review_notes}
                </div>
              )}
            </div>
          )}

          {/* Phase 5: Task Assignment, Acknowledgement, SLA & Resolution Lifecycle */}
          <div className="p-4 rounded-xl bg-slate-950/90 border border-slate-800 space-y-3.5 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="font-extrabold text-slate-200 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-sky-400" />
                Staff Assignment &amp; Follow-up Lifecycle
              </span>
              <div className="flex items-center gap-2 text-[10px]">
                <span className="text-slate-400">SLA: <strong className="text-sky-300">{ticket.sla_minutes || 60}m</strong></span>
                {ticket.deadline_at && (
                  <span className="text-slate-400">Deadline: <strong className="text-amber-300">{new Date(ticket.deadline_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong></span>
                )}
              </div>
            </div>

            {/* 1. Staff and Team Assignment */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-900/80 border border-slate-800">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Assigned Staff &amp; Team</span>
                <span className="text-slate-200 font-semibold mt-0.5 block">
                  {ticket.assigned_staff && ticket.assigned_staff !== 'Unassigned' ? ticket.assigned_staff : 'Unassigned to Individual'}
                  <span className="text-slate-400 font-normal ml-1">({ticket.assigned_team || ticket.department})</span>
                </span>
              </div>
              {onAssign && (
                <button
                  onClick={() => setShowAssignForm(!showAssignForm)}
                  className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
                >
                  {showAssignForm ? 'Cancel' : 'Reassign Staff / Team'}
                </button>
              )}
            </div>

            {showAssignForm && onAssign && (
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-700 space-y-2">
                <span className="text-[10px] uppercase font-bold text-sky-400 block">Reassign Task:</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={assigneeName}
                    onChange={(e) => setAssigneeName(e.target.value)}
                    placeholder="Staff Member (e.g. Nurse Sarah Jenkins)"
                    className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white"
                  />
                  <input
                    type="text"
                    value={assignTeam}
                    onChange={(e) => setAssignTeam(e.target.value)}
                    placeholder="Team / Unit (e.g. Floor Charge Nursing)"
                    className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white"
                  />
                </div>
                <button
                  onClick={handleAssignSubmit}
                  disabled={isActionLoading}
                  className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs transition-all disabled:opacity-50"
                >
                  Save Assignment
                </button>
              </div>
            )}

            {/* 2. Acknowledgement Section */}
            {ticket.is_acknowledged ? (
              <div className="p-2.5 rounded-lg bg-emerald-950/30 border border-emerald-500/30 flex items-center justify-between text-emerald-200">
                <div className="flex items-center gap-2">
                  <CheckCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div>
                    <span className="font-bold text-[11px] block text-emerald-300">
                      Receipt Acknowledged by {ticket.acknowledged_by || 'Assigned Staff'}
                    </span>
                    <span className="text-[10px] text-emerald-400">
                      {ticket.acknowledged_at ? new Date(ticket.acknowledged_at).toLocaleString() : 'Acknowledged'}
                    </span>
                  </div>
                </div>
                <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                  ACK VERIFIED
                </span>
              </div>
            ) : !isTerminalStatus(ticket.status) && onAcknowledge ? (
              <div className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-500/40 space-y-2">
                <div className="flex items-center justify-between text-amber-300 text-[11px] font-bold">
                  <span>Awaiting Staff Acknowledgement</span>
                  <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono">
                    UNACKNOWLEDGED
                  </span>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={ackStaff}
                    onChange={(e) => setAckStaff(e.target.value)}
                    placeholder="Your Name / Staff ID"
                    className="flex-1 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white"
                  />
                  <button
                    onClick={handleAckSubmit}
                    disabled={isActionLoading}
                    className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-1 transition-all disabled:opacity-50"
                  >
                    <CheckCheck className="w-3.5 h-3.5" />
                    <span>Acknowledge Receipt</span>
                  </button>
                </div>
              </div>
            ) : null}

            {/* 3. Escalation Section */}
            {ticket.escalation_level && ticket.escalation_level > 0 ? (
              <div className="p-3 rounded-lg bg-orange-950/40 border border-orange-500/50 space-y-1.5">
                <div className="flex items-center justify-between font-bold text-orange-400">
                  <span className="flex items-center gap-1.5">
                    <Flame className="w-4 h-4 text-orange-400" />
                    ESCALATED &bull; LEVEL {ticket.escalation_level}
                  </span>
                  <span className="text-[10px] text-orange-300 font-mono">
                    {ticket.escalated_at ? new Date(ticket.escalated_at).toLocaleString() : ''}
                  </span>
                </div>
                <div className="p-2 rounded bg-orange-950/70 border border-orange-800/50 text-[11px] font-mono text-orange-100 whitespace-pre-line">
                  {ticket.escalation_reason || 'Escalated due to response SLA delay or clinical complexity.'}
                </div>
              </div>
            ) : null}

            {!isTerminalStatus(ticket.status) && onEscalate && (
              <div>
                {!showEscalateForm ? (
                  <button
                    onClick={() => setShowEscalateForm(true)}
                    className="text-orange-400 hover:text-orange-300 font-semibold text-xs flex items-center gap-1 transition-colors"
                  >
                    <Flame className="w-3.5 h-3.5" />
                    <span>Escalate this Task to Charge Nurse / Supervisor</span>
                  </button>
                ) : (
                  <div className="p-3 rounded-lg bg-orange-950/30 border border-orange-500/40 space-y-2">
                    <span className="text-[10px] uppercase font-bold text-orange-400 block">Record Escalation Directive:</span>
                    <input
                      type="text"
                      value={escalateStaff}
                      onChange={(e) => setEscalateStaff(e.target.value)}
                      placeholder="Escalating Staff / Supervisor Role"
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white"
                    />
                    <textarea
                      value={escalateReason}
                      onChange={(e) => setEscalateReason(e.target.value)}
                      placeholder="Reason for escalation (e.g. no response in 15 min, acute deterioration)..."
                      rows={2}
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white resize-none"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleEscalateSubmit}
                        disabled={!escalateReason.trim() || isActionLoading}
                        className="px-3.5 py-1.5 rounded-lg bg-orange-600 hover:bg-orange-500 text-white font-semibold text-xs transition-all disabled:opacity-50"
                      >
                        Confirm Escalation
                      </button>
                      <button
                        onClick={() => setShowEscalateForm(false)}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs hover:text-white"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 4. Resolution Tracking Section */}
            {ticket.status === 'RESOLVED' ? (
              <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-500/40 space-y-1.5">
                <div className="flex items-center justify-between font-bold text-emerald-400">
                  <span className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    CLINICAL RESOLUTION RECORDED
                  </span>
                  <span className="text-[10px] text-emerald-300 font-mono">
                    {ticket.resolved_at ? new Date(ticket.resolved_at).toLocaleString() : ''}
                  </span>
                </div>
                <div className="text-[11px] text-slate-300">
                  <strong>Signed off by:</strong> {ticket.resolved_by || 'Staff Member'}
                </div>
                <div className="p-2 rounded bg-slate-950 border border-slate-800 text-xs text-emerald-100 whitespace-pre-line leading-relaxed">
                  {ticket.resolution_notes || 'Task completed per clinical hospital protocol.'}
                </div>
              </div>
            ) : onResolve ? (
              <div>
                {!showResolveForm ? (
                  <button
                    onClick={() => setShowResolveForm(true)}
                    className="text-emerald-400 hover:text-emerald-300 font-semibold text-xs flex items-center gap-1 transition-colors"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Complete &amp; Resolve Task with Clinical Sign-Off</span>
                  </button>
                ) : (
                  <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 space-y-2">
                    <span className="text-[10px] uppercase font-bold text-emerald-400 block">Resolution Verification Sign-off:</span>
                    <input
                      type="text"
                      value={resolverName}
                      onChange={(e) => setResolverName(e.target.value)}
                      placeholder="Resolving Staff Name / Nurse Role"
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white"
                    />
                    <textarea
                      value={resolveNotes}
                      onChange={(e) => setResolveNotes(e.target.value)}
                      placeholder="Document clinical resolution notes (e.g. vital signs checked, medication administered)..."
                      rows={2}
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white resize-none"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleResolveSubmit}
                        disabled={!resolveNotes.trim() || isActionLoading}
                        className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-all disabled:opacity-50"
                      >
                        Submit Resolution
                      </button>
                      <button
                        onClick={() => setShowResolveForm(false)}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs hover:text-white"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : null}

          </div>

          {/* Phase 3: Category, Intent, Deadline, & Confidence */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Standard Category</span>
              <span className="text-sky-300 font-semibold block mt-0.5">
                {ticket.category || 'Nursing and patient care'}
              </span>
              <span className="text-[10px] text-slate-500 font-mono block mt-0.5">
                intent: {ticket.intent || 'general_request'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Explicit Deadline</span>
              <span className="font-semibold block mt-0.5 text-amber-300">
                {ticket.explicit_deadline ? (
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-amber-400" />
                    {ticket.explicit_deadline}
                  </span>
                ) : (
                  <span className="text-slate-500 italic font-normal">None stated in call</span>
                )}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Triage Confidence</span>
              <div className="flex items-center gap-2 mt-1">
                <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full rounded-full transition-all"
                    style={{ width: `${Math.round((ticket.confidence_score || 0.95) * 100)}%` }}
                  />
                </div>
                <span className="text-slate-300 font-bold text-[11px]">
                  {Math.round((ticket.confidence_score || 0.95) * 100)}%
                </span>
              </div>
            </div>
          </div>

          {/* Specialized Domain Verification Cards */}
          {isAppointmentRequest && (
            <div className={`p-3.5 rounded-xl border text-xs ${
              ticket.status === 'RESOLVED'
                ? 'bg-emerald-950/30 border-emerald-500/50 text-emerald-200'
                : 'bg-amber-950/30 border-amber-500/50 text-amber-200'
            }`}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-extrabold text-[11px] uppercase flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-amber-400" />
                  <span>Outpatient (OPD) Appointment Coordination</span>
                </span>
                <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                  ticket.status === 'RESOLVED' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                }`}>
                  {ticket.status === 'RESOLVED' ? 'CONFIRMED' : 'AWAITING CONFIRMATION'}
                </span>
              </div>
              <p className="text-slate-300 leading-relaxed text-[11px]">
                {ticket.status === 'RESOLVED'
                  ? `Appointment confirmed per clinical sign-off: "${ticket.resolution_notes || 'Confirmed with attending clinic'}" by ${ticket.resolved_by || 'Staff'}.`
                  : 'ATTENTION: This appointment request has NOT yet been confirmed by the OPD department. Do not communicate confirmation to the patient until the assigned clinic team marks this task as Resolved.'}
              </p>
              {ticket.explicit_deadline && (
                <div className="mt-1.5 text-[11px] text-amber-300 font-medium">
                  Requested Timeframe: <strong>{ticket.explicit_deadline}</strong>
                </div>
              )}
            </div>
          )}

          {isBillingOrInsurance && (
            <div className={`p-3.5 rounded-xl border text-xs ${
              ticket.status === 'RESOLVED'
                ? 'bg-emerald-950/30 border-emerald-500/50 text-emerald-200'
                : 'bg-indigo-950/30 border-indigo-500/50 text-indigo-200'
            }`}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-extrabold text-[11px] uppercase flex items-center gap-1.5">
                  <CreditCard className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Patient Billing &amp; Insurance Pre-Authorisation</span>
                </span>
                <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                  ticket.status === 'RESOLVED' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-indigo-500/20 text-indigo-300'
                }`}>
                  {ticket.status === 'RESOLVED' ? 'FINANCIAL CLEARANCE CONFIRMED' : 'PENDING ACCOUNTS REVIEW'}
                </span>
              </div>
              <p className="text-slate-300 leading-relaxed text-[11px]">
                {ticket.status === 'RESOLVED'
                  ? `Financial clearance confirmed: "${ticket.resolution_notes || 'Accounts verified'}" by ${ticket.resolved_by || 'Staff'}.`
                  : 'Under verification with hospital billing / TPA desk. Ensure claim details match patient file before communicating.'}
              </p>
            </div>
          )}

          {isFollowUpCommitment && (
            <div className={`p-3.5 rounded-xl border text-xs ${
              ticket.is_overdue
                ? 'bg-red-950/40 border-red-500/60 text-red-200 animate-pulse'
                : 'bg-sky-950/30 border-sky-500/50 text-sky-200'
            }`}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-extrabold text-[11px] uppercase flex items-center gap-1.5">
                  <PhoneCall className={`w-3.5 h-3.5 ${ticket.is_overdue ? 'text-red-400' : 'text-sky-400'}`} />
                  <span>Promised Clinical Callback Commitment</span>
                </span>
                <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                  ticket.is_overdue ? 'bg-red-600 text-white' : 'bg-sky-500/20 text-sky-300'
                }`}>
                  {ticket.is_overdue ? 'OVERDUE' : 'ACTIVE SLA'}
                </span>
              </div>
              <p className="text-slate-300 leading-relaxed text-[11px]">
                {ticket.is_overdue
                  ? `DEADLINE BREACHED: Callback promised for "${ticket.explicit_deadline || 'within SLA'}" has not been signed off. Immediate callback required.`
                  : `Staff promised to follow up with patient/caller. Target window: ${ticket.explicit_deadline || 'within triage SLA window'}.`}
              </p>
            </div>
          )}

          {/* Required Action Card */}
          {ticket.required_action && (
            <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/30">
              <span className="text-[10px] uppercase font-extrabold text-emerald-400 block mb-1 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                Required Clinical / Staff Action:
              </span>
              <p className="text-xs text-emerald-100 font-medium leading-relaxed">
                {ticket.required_action}
              </p>
            </div>
          )}

          {/* Priority Rationale Card */}
          {ticket.priority_rationale && (
            <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800">
              <span className="text-[10px] uppercase font-bold text-sky-400 block mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5 text-sky-400" />
                Priority Triage Rationale:
              </span>
              <p className="text-xs text-slate-300 leading-relaxed">
                {ticket.priority_rationale}
              </p>
            </div>
          )}

          {/* Phase 4: Safe Clinical Urgency & Human Review Evidence */}
          {(ticket.requires_human_review || ticket.urgency_evidence) && (
            <div className={`p-3.5 rounded-xl border ${
              ticket.requires_human_review
                ? 'bg-amber-950/30 border-amber-500/40'
                : 'bg-slate-950/80 border-slate-800'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] uppercase font-extrabold block flex items-center gap-1.5 text-amber-300">
                  <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                  Clinical Urgency Evidence &amp; Safety Audit:
                </span>
                {ticket.requires_human_review && (
                  <span className="px-2 py-0.5 rounded text-[9px] font-black bg-amber-500/20 text-amber-300 border border-amber-500/50 uppercase">
                    HUMAN REVIEW MANDATORY
                  </span>
                )}
              </div>

              {ticket.human_review_reason && (
                <div className="p-2.5 rounded-lg bg-amber-900/30 border border-amber-600/40 text-xs text-amber-200 mb-2 leading-relaxed">
                  <span className="font-bold block text-[10px] uppercase text-amber-400 mb-0.5">Clinical Review Indication:</span>
                  {ticket.human_review_reason}
                </div>
              )}

              {ticket.urgency_evidence && (
                <div className="space-y-1.5 text-xs text-slate-300">
                  {ticket.urgency_evidence.evidence_summary && (
                    <p className="text-[11px] text-slate-300 font-medium">
                      <strong className="text-slate-200">Evidence Summary:</strong> {ticket.urgency_evidence.evidence_summary}
                    </p>
                  )}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 pt-2 border-t border-slate-800/80 text-[11px]">
                    {ticket.urgency_evidence.active_symptoms?.length > 0 && (
                      <div>
                        <span className="text-slate-400 font-medium block">Active Acute Symptoms:</span>
                        <span className="text-red-300 font-semibold">{ticket.urgency_evidence.active_symptoms.join(', ')}</span>
                      </div>
                    )}
                    {ticket.urgency_evidence.negated_symptoms?.length > 0 && (
                      <div>
                        <span className="text-slate-400 font-medium block">Negated / Ruled-Out:</span>
                        <span className="text-emerald-300 font-semibold">{ticket.urgency_evidence.negated_symptoms.join(', ')}</span>
                      </div>
                    )}
                    {ticket.urgency_evidence.refractory_markers?.length > 0 && (
                      <div>
                        <span className="text-slate-400 font-medium block">Refractory Markers:</span>
                        <span className="text-amber-300 font-semibold">{ticket.urgency_evidence.refractory_markers.join(', ')}</span>
                      </div>
                    )}
                    {ticket.urgency_evidence.historical_qualifiers?.length > 0 && (
                      <div>
                        <span className="text-slate-400 font-medium block">Historical Qualifiers:</span>
                        <span className="text-slate-300 font-semibold">{ticket.urgency_evidence.historical_qualifiers.join(', ')}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

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

          {/* Parent Call Structured Clinical Summary & Sibling Tasks */}
          {parentCall && (
            <div className="p-3.5 rounded-xl bg-slate-950 border border-sky-500/30 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="font-bold text-xs uppercase text-sky-300 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                  <span>Originating Call Context &amp; Structured Summary (Call #{parentCall.id})</span>
                </span>
                <span className="text-[10px] text-slate-400">
                  {new Date(parentCall.created_at).toLocaleString()}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-sky-950/30 border border-sky-800/40 text-xs text-sky-100">
                <span className="font-bold block text-[10px] uppercase text-sky-400 mb-0.5">AI Clinical Synthesis:</span>
                {parentCall.summary}
              </div>

              {parentCall.tickets && parentCall.tickets.length > 1 && (
                <div>
                  <span className="font-bold block text-[10px] uppercase text-slate-400 mb-1.5 flex items-center gap-1">
                    <Layers className="w-3 h-3 text-teal-400" />
                    Other Tasks Extracted from this Same Call ({parentCall.tickets.length - 1}):
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {parentCall.tickets
                      .filter((sib) => sib.id !== ticket.id)
                      .map((sib) => (
                        <button
                          key={sib.id}
                          onClick={() => onSelectSiblingTicket && onSelectSiblingTicket(sib)}
                          className="p-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-sky-500 text-left text-xs transition-colors flex items-center justify-between group"
                        >
                          <div className="truncate pr-2">
                            <span className="text-[10px] font-bold text-sky-400 block truncate">{sib.department}</span>
                            <span className="text-slate-200 font-medium truncate block">{sib.title}</span>
                          </div>
                          <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-sky-400 shrink-0" />
                        </button>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

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
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="font-semibold text-slate-300">{log.action}: </span>
                        {log.actor && (
                          <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                            log.actor.includes('AI')
                              ? 'bg-purple-950/80 text-purple-300 border border-purple-500/30'
                              : 'bg-sky-950/80 text-sky-300 border border-sky-500/30'
                          }`}>
                            {log.actor}
                          </span>
                        )}
                      </div>
                      <span className="text-slate-400">{log.note}</span>
                    </div>
                    <span className="text-[10px] text-slate-500 whitespace-nowrap">
                      {log.created_at ? new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
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
