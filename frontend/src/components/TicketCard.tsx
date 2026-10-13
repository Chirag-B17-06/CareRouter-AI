import React from 'react';
import {
  AlertOctagon,
  Stethoscope,
  Pill,
  Utensils,
  Wrench,
  ClipboardList,
  User,
  Bed,
  ArrowRight,
  ShieldAlert,
  MessageSquare,
  Languages,
  Trash2,
  Clock,
  CheckCheck,
  Flame,
  Timer,
  AlertTriangle,
  Calendar,
  CreditCard,
  PhoneCall
} from 'lucide-react';
import { Ticket, TicketStatus, UrgencyTier } from '../types';

interface TicketCardProps {
  ticket: Ticket;
  onSelect: (ticket: Ticket) => void;
  onUpdateStatus: (ticketId: number, nextStatus: TicketStatus) => void;
  onDelete?: (ticketId: number) => void;
  onAcknowledge?: (ticketId: number) => void;
}

export const TicketCard: React.FC<TicketCardProps> = ({
  ticket,
  onSelect,
  onUpdateStatus,
  onDelete,
  onAcknowledge
}) => {
  // Department Icon and Accent color
  const getDeptConfig = (dept: string) => {
    if (dept.includes('Rapid Response') || dept.includes('Critical')) {
      return { icon: AlertOctagon, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' };
    }
    if (dept.includes('Nursing')) {
      return { icon: Stethoscope, color: 'text-sky-400', bg: 'bg-sky-500/10 border-sky-500/20' };
    }
    if (dept.includes('Pharmacy')) {
      return { icon: Pill, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' };
    }
    if (dept.includes('Dietary')) {
      return { icon: Utensils, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' };
    }
    if (dept.includes('Facilities') || dept.includes('Environmental')) {
      return { icon: Wrench, color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/20' };
    }
    return { icon: ClipboardList, color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/20' };
  };

  const deptConfig = getDeptConfig(ticket.department);
  const DeptIcon = deptConfig.icon;

  // Urgency styling
  const getUrgencyBadge = (urgency: UrgencyTier) => {
    switch (urgency) {
      case 'STAT_EMERGENCY':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-extrabold bg-red-600/20 text-red-300 border border-red-500/50 shadow-sm animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
            STAT EMERGENCY
          </span>
        );
      case 'URGENT':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
            URGENT (15m SLA)
          </span>
        );
      case 'ROUTINE':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-sky-500/15 text-sky-300 border border-sky-500/30">
            ROUTINE
          </span>
        );
      case 'INQUIRY':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">
            INQUIRY
          </span>
        );
    }
  };

  const getLanguageLabel = (lang?: string) => {
    if (lang === 'kn') return { label: 'ಕನ್ನಡ', class: 'kannada-text bg-purple-500/10 text-purple-300 border-purple-500/30' };
    if (lang === 'hi') return { label: 'हिन्दी', class: 'hindi-text bg-orange-500/10 text-orange-300 border-orange-500/30' };
    return { label: 'English', class: 'bg-sky-500/10 text-sky-300 border-sky-500/30' };
  };

  const langInfo = getLanguageLabel(ticket.language);

  // Status Badge and Next action
  const getNextStatus = (current: TicketStatus): TicketStatus | null => {
    if (current === 'PENDING') return 'IN_PROGRESS';
    if (current === 'IN_PROGRESS') return 'DISPATCHED';
    if (current === 'DISPATCHED') return 'RESOLVED';
    return null;
  };

  const nextStatus = getNextStatus(ticket.status);

  const getStatusColor = (status: TicketStatus) => {
    switch (status) {
      case 'PENDING':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'IN_PROGRESS':
        return 'bg-sky-500/10 text-sky-400 border-sky-500/30';
      case 'DISPATCHED':
        return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
      case 'RESOLVED':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
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

  return (
    <div
      className={`glass-card rounded-xl p-4 transition-all duration-200 flex flex-col justify-between hover:shadow-xl relative ${
        isStat
          ? 'border-red-500/50 bg-red-950/15 stat-pulse hover:border-red-400'
          : 'border-slate-800 bg-slate-900/60'
      }`}
    >
      <div>
        {/* Top Badges Header */}
        <div className="flex items-center justify-between gap-2 mb-2.5">
          <div className="flex items-center gap-1.5">
            <span className={`p-1.5 rounded-lg border flex items-center justify-center ${deptConfig.bg} ${deptConfig.color}`}>
              <DeptIcon className="w-3.5 h-3.5" />
            </span>
            <span className="text-[11px] font-semibold text-slate-300 truncate max-w-[130px]">
              {ticket.assigned_team || ticket.department}
            </span>
          </div>

          <div className="flex items-center gap-1.5 flex-wrap justify-end">
            {ticket.requires_human_review && !ticket.is_reviewed && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-black bg-amber-950/90 text-amber-300 border border-amber-500/70 shadow-sm animate-pulse">
                <ShieldAlert className="w-2.5 h-2.5 text-amber-400" />
                NEEDS REVIEW
              </span>
            )}
            {ticket.is_overdue && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-black bg-rose-950/80 text-rose-300 border border-rose-500/70 shadow-sm animate-pulse">
                <Timer className="w-2.5 h-2.5 text-rose-400" />
                OVERDUE
              </span>
            )}
            {Boolean(ticket.escalation_level && ticket.escalation_level > 0) && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-black bg-orange-950/80 text-orange-300 border border-orange-500/70 shadow-sm">
                <Flame className="w-2.5 h-2.5 text-orange-400" />
                L{ticket.escalation_level}
              </span>
            )}
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${langInfo.class}`}>
              {langInfo.label}
            </span>
            {getUrgencyBadge(ticket.urgency)}
          </div>
        </div>

        {/* Patient & Room Info */}
        <div className="flex items-center justify-between text-xs py-1.5 px-2 rounded-lg bg-slate-950/60 border border-slate-800/80 mb-2.5">
          <div className="flex items-center gap-1 text-slate-300 font-semibold truncate">
            <Bed className="w-3.5 h-3.5 text-sky-400" />
            <span>{ticket.room_number}</span>
          </div>
          <div className="flex items-center gap-1 text-slate-400 truncate max-w-[140px]">
            <User className="w-3 h-3 text-slate-500" />
            <span>{ticket.patient_name}</span>
          </div>
        </div>

        {/* Category & Explicit Deadline Bar */}
        {ticket.category && (
          <div className="flex items-center justify-between gap-1 mb-2">
            <span className="text-[10px] font-semibold text-sky-300 bg-sky-950/60 border border-sky-800/60 px-2 py-0.5 rounded truncate max-w-[190px]">
              {ticket.category}
            </span>
            {ticket.explicit_deadline ? (
              <span className="text-[10px] font-bold text-amber-300 bg-amber-950/70 border border-amber-600/50 px-2 py-0.5 rounded flex items-center gap-1 shrink-0">
                <Clock className="w-2.5 h-2.5 text-amber-400" />
                <span>{ticket.explicit_deadline}</span>
              </span>
            ) : null}
          </div>
        )}

        {/* Title */}
        <h3 className="text-sm font-bold text-white line-clamp-2 leading-snug mb-1.5">
          {ticket.title}
        </h3>

        {/* Human Clinical Review Flag & Verification */}
        {ticket.requires_human_review && !ticket.is_reviewed && (
          <div className="p-2 rounded-lg bg-amber-500/15 border border-amber-500/40 text-[11px] text-amber-200 mb-2 flex items-start gap-1.5 animate-pulse">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
            <div className="leading-snug">
              <span className="text-[9px] uppercase font-black text-amber-300 block">HUMAN REVIEW REQUIRED</span>
              {ticket.human_review_reason || 'Clinical diagnostic uncertainty detected. Human nurse evaluation required.'}
            </div>
          </div>
        )}

        {/* Specialized Domain Actual Status Indicators */}
        {isAppointmentRequest && (
          <div className={`p-2 rounded-lg border text-[11px] mb-2 ${
            ticket.status === 'RESOLVED'
              ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-200'
              : 'bg-amber-950/30 border-amber-500/40 text-amber-200'
          }`}>
            <div className="flex items-center justify-between font-bold text-[10px] uppercase mb-0.5">
              <span className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-amber-400" />
                <span>OPD Appointment Coordination</span>
              </span>
              <span className={`px-1.5 py-0.2 rounded text-[9px] font-black ${
                ticket.status === 'RESOLVED' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
              }`}>
                {ticket.status === 'RESOLVED' ? 'CONFIRMED' : 'UNCONFIRMED'}
              </span>
            </div>
            <p className="text-[10px] text-slate-300">
              {ticket.status === 'RESOLVED'
                ? 'Appointment verified & scheduled per clinic sign-off.'
                : 'Awaiting clinic OPD confirmation — do not assume confirmed.'}
            </p>
          </div>
        )}

        {isBillingOrInsurance && (
          <div className={`p-2 rounded-lg border text-[11px] mb-2 ${
            ticket.status === 'RESOLVED'
              ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-200'
              : 'bg-indigo-950/30 border-indigo-500/40 text-indigo-200'
          }`}>
            <div className="flex items-center justify-between font-bold text-[10px] uppercase mb-0.5">
              <span className="flex items-center gap-1.5">
                <CreditCard className="w-3.5 h-3.5 text-indigo-400" />
                <span>Billing / Insurance Claim</span>
              </span>
              <span className={`px-1.5 py-0.2 rounded text-[9px] font-black ${
                ticket.status === 'RESOLVED' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-indigo-500/20 text-indigo-300'
              }`}>
                {ticket.status === 'RESOLVED' ? 'SETTLED' : 'PENDING ACCOUNTS'}
              </span>
            </div>
            <p className="text-[10px] text-slate-300">
              {ticket.status === 'RESOLVED'
                ? 'Financial clearance confirmed with patient accounts.'
                : 'Under verification with hospital billing / TPA desk.'}
            </p>
          </div>
        )}

        {isFollowUpCommitment && (
          <div className={`p-2 rounded-lg border text-[11px] mb-2 ${
            ticket.is_overdue
              ? 'bg-red-950/40 border-red-500/60 text-red-200 animate-pulse'
              : 'bg-sky-950/30 border-sky-500/40 text-sky-200'
          }`}>
            <div className="flex items-center justify-between font-bold text-[10px] uppercase mb-0.5">
              <span className="flex items-center gap-1.5">
                <PhoneCall className={`w-3.5 h-3.5 ${ticket.is_overdue ? 'text-red-400' : 'text-sky-400'}`} />
                <span>Promised Callback Commitment</span>
              </span>
              <span className={`px-1.5 py-0.2 rounded text-[9px] font-black ${
                ticket.is_overdue ? 'bg-red-600 text-white' : 'bg-sky-500/20 text-sky-300'
              }`}>
                {ticket.is_overdue ? 'OVERDUE' : 'ACTIVE SLA'}
              </span>
            </div>
            <p className="text-[10px] text-slate-300">
              Target window: <strong className={ticket.is_overdue ? 'text-red-300' : 'text-sky-300'}>{ticket.explicit_deadline || 'Per triage SLA window'}</strong>
            </p>
          </div>
        )}

        {/* Required Action Directive */}
        {ticket.required_action && (
          <div className="p-2 rounded-lg bg-slate-950/70 border border-emerald-500/20 text-[11px] text-slate-200 mb-2 leading-snug">
            <span className="text-[9px] uppercase font-bold text-emerald-400 block mb-0.5">Required Action:</span>
            {ticket.required_action}
          </div>
        )}

        {/* Extracted Phone Call Raw Quote in Original Script */}
        {ticket.raw_quote && (
          <div className={`p-2.5 rounded-md bg-slate-950/50 border-l-2 border-sky-500/70 text-slate-200 text-xs italic line-clamp-3 mb-2.5 leading-relaxed ${
            ticket.language === 'kn' ? 'kannada-text' : ticket.language === 'hi' ? 'hindi-text' : ''
          }`}>
            &ldquo;{ticket.raw_quote}&rdquo;
          </div>
        )}

        {/* Clinical Flags Pills */}
        {ticket.clinical_flags && ticket.clinical_flags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {ticket.clinical_flags.map((flag, idx) => (
              <span
                key={idx}
                className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60 flex items-center gap-0.5"
              >
                <ShieldAlert className="w-2.5 h-2.5 text-amber-400" />
                {flag.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Card Footer & Controls */}
      <div className="pt-2.5 border-t border-slate-800/80 space-y-2 mt-2">
        <div className="flex items-center justify-between text-[11px] text-slate-400">
          <span className="truncate max-w-[170px]">
            Staff: <span className="text-slate-300 font-medium">
              {ticket.assigned_staff && ticket.assigned_staff !== 'Unassigned' ? ticket.assigned_staff : ticket.assigned_to}
            </span>
          </span>
          <div className="flex items-center gap-1">
            {ticket.is_acknowledged ? (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-950/70 text-emerald-300 border border-emerald-600/50 flex items-center gap-0.5">
                <CheckCheck className="w-2.5 h-2.5 text-emerald-400" /> ACK
              </span>
            ) : ticket.status !== 'RESOLVED' ? (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-amber-950/60 text-amber-400 border border-amber-600/40">
                UNACK
              </span>
            ) : null}
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${getStatusColor(ticket.status)}`}>
              {ticket.status.replace(/_/g, ' ')}
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={() => onSelect(ticket)}
            id={`inspect-ticket-${ticket.id}-btn`}
            className="flex-1 py-1.5 px-2.5 rounded-lg border border-slate-800 bg-slate-950/60 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center justify-center gap-1"
          >
            <MessageSquare className="w-3 h-3 text-sky-400" />
            <span>Details &amp; Notes</span>
          </button>

          {!ticket.is_acknowledged && ticket.status !== 'RESOLVED' && onAcknowledge && (
            <button
              onClick={() => onAcknowledge(ticket.id)}
              id={`ack-ticket-${ticket.id}-btn`}
              className="py-1.5 px-2.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/50 text-emerald-300 text-xs font-semibold flex items-center justify-center gap-1 transition-all"
              title="Acknowledge Task Receipt"
            >
              <CheckCheck className="w-3 h-3" />
              <span>Ack</span>
            </button>
          )}

          {nextStatus && (
            <button
              onClick={() => onUpdateStatus(ticket.id, nextStatus)}
              id={`advance-ticket-${ticket.id}-btn`}
              className={`py-1.5 px-2.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition-all ${
                nextStatus === 'RESOLVED'
                  ? 'bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-600/30'
                  : 'bg-sky-600/20 border border-sky-500/40 text-sky-300 hover:bg-sky-600/30'
              }`}
              title={`Advance to ${nextStatus}`}
            >
              <span>{nextStatus.replace(/_/g, ' ')}</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          )}

          {ticket.status === 'RESOLVED' && onDelete && (
            <button
              onClick={() => {
                if (window.confirm(`Delete resolved ticket #${ticket.id} (${ticket.title})?\n\nThis will remove the ticket from the system.`)) {
                  onDelete(ticket.id);
                }
              }}
              id={`delete-ticket-${ticket.id}-btn`}
              className="py-1.5 px-2.5 rounded-lg bg-red-950/40 hover:bg-red-900/60 border border-red-500/40 text-red-300 hover:text-white text-xs font-semibold flex items-center justify-center gap-1 transition-colors"
              title="Delete resolved ticket"
            >
              <Trash2 className="w-3 h-3 text-red-400" />
              <span>Delete</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
