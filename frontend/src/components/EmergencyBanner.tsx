import React from 'react';
import { AlertOctagon, ArrowRight, ShieldAlert } from 'lucide-react';
import { Ticket } from '../types';

interface EmergencyBannerProps {
  emergencyTickets: Ticket[];
  onSelectTicket: (ticket: Ticket) => void;
}

export const EmergencyBanner: React.FC<EmergencyBannerProps> = ({
  emergencyTickets,
  onSelectTicket
}) => {
  if (emergencyTickets.length === 0) return null;

  const topEmergency = emergencyTickets[0];

  return (
    <div
      id="emergency-alert-banner"
      className="w-full bg-gradient-to-r from-red-950/80 via-red-900/60 to-red-950/80 border-y sm:border sm:rounded-xl border-red-500/50 p-3 sm:p-4 my-4 shadow-xl shadow-red-950/40 relative overflow-hidden animate-fade-in"
    >
      {/* Background emergency glow pulse */}
      <div className="absolute inset-0 bg-red-600/10 animate-pulse pointer-events-none" />

      <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-3">
        
        {/* Warning Icon & Text */}
        <div className="flex items-start md:items-center space-x-3">
          <div className="p-2 rounded-lg bg-red-600/20 text-red-400 border border-red-500/30 shrink-0 animate-bounce">
            <AlertOctagon className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 rounded text-[11px] font-extrabold tracking-wider bg-red-600 text-white uppercase shadow-sm">
                STAT EMERGENCY ALERT
              </span>
              <span className="text-xs font-semibold text-red-200">
                {emergencyTickets.length} Critical Incident{emergencyTickets.length > 1 ? 's' : ''} Awaiting Triage
              </span>
            </div>
            <p className="text-sm font-semibold text-white mt-0.5">
              {topEmergency.patient_name} &bull; {topEmergency.room_number}: <span className="text-red-300 font-normal">{topEmergency.title}</span>
            </p>
            <p className="text-xs text-red-300/80 mt-0.5 line-clamp-1 italic">
              &ldquo;{topEmergency.raw_quote || topEmergency.description}&rdquo;
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-2 shrink-0 self-end md:self-center">
          <button
            onClick={() => onSelectTicket(topEmergency)}
            id="acknowledge-stat-alert-btn"
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold shadow-md shadow-red-600/30 transition-transform active:scale-95"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Acknowledge STAT Ticket</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

      </div>
    </div>
  );
};
