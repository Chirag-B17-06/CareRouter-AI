import React from 'react';
import {
  AlertOctagon,
  Stethoscope,
  Pill,
  Utensils,
  Wrench,
  ClipboardList,
  Clock,
  User,
  Bed,
  CheckCircle,
  ArrowRight,
  ShieldAlert,
  MessageSquare
} from 'lucide-react';
import { Ticket, TicketStatus, UrgencyTier } from '../types';

interface TicketCardProps {
  ticket: Ticket;
  onSelect: (ticket: Ticket) => void;
  onUpdateStatus: (ticketId: number, nextStatus: TicketStatus) => void;
}

export const TicketCard: React.FC<TicketCardProps> = ({
  ticket,
  onSelect,
  onUpdateStatus
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
            <span className="text-[11px] font-semibold text-slate-300 truncate max-w-[150px]">
              {ticket.department}
            </span>
          </div>
          {getUrgencyBadge(ticket.urgency)}
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

        {/* Title */}
        <h3 className="text-sm font-bold text-white line-clamp-2 leading-snug mb-1.5">
          {ticket.title}
        </h3>

        {/* Extracted Phone Call Raw Quote */}
        {ticket.raw_quote && (
          <div className="p-2 rounded-md bg-slate-950/40 border-l-2 border-sky-500/60 text-slate-300 text-xs italic line-clamp-2 mb-2.5">
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
          <span className="truncate max-w-[160px]">Role: <span className="text-slate-300 font-medium">{ticket.assigned_to}</span></span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${getStatusColor(ticket.status)}`}>
            {ticket.status.replace(/_/g, ' ')}
          </span>
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
        </div>
      </div>
    </div>
  );
};
