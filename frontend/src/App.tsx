import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchTickets,
  fetchAnalytics,
  updateTicket,
  addTicketNote,
  deleteTicket,
  acknowledgeTicket,
  assignTicket,
  escalateTicket,
  resolveTicket,
  checkEscalations,
  reviewTicket,
  fetchCalls
} from './services/api';
import { Ticket, AnalyticsData, ProcessCallResult, TicketStatus, Call } from './types';
import { Navbar } from './components/Navbar';
import { EmergencyBanner } from './components/EmergencyBanner';
import { TicketBoard } from './components/TicketBoard';
import { AudioRecorder } from './components/AudioRecorder';
import { TicketDetailModal } from './components/TicketDetailModal';
import { AnalyticsModal } from './components/AnalyticsModal';
import { ShiftHandoverModal } from './components/ShiftHandoverModal';
import { CallsExplorer } from './components/CallsExplorer';
import { soundManager } from './utils/audio';
import {
  Activity,
  AlertOctagon,
  CheckCircle2,
  Clock,
  Layers,
  Mic,
  ShieldCheck,
  Sparkles,
  Timer
} from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'board' | 'calls' | 'record' | 'analytics'>('board');
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [backendError, setBackendError] = useState<string | null>(null);

  // Audio alerts mute state
  const [isMuted, setIsMuted] = useState<boolean>(false);

  // Modals state
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [isAnalyticsOpen, setIsAnalyticsOpen] = useState<boolean>(false);
  const [isShiftHandoverOpen, setIsShiftHandoverOpen] = useState<boolean>(false);

  // Notification toast
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4500);
  };

  // Load all dashboard tickets, analytics & calls from FastAPI backend
  const loadDashboardData = useCallback(async () => {
    try {
      setBackendError(null);
      // Proactively check overdue tasks for auto-escalation
      await checkEscalations().catch(() => {});
      const [ticketsData, analyticsData, callsData] = await Promise.all([
        fetchTickets(),
        fetchAnalytics(),
        fetchCalls().catch(() => [])
      ]);
      setTickets(ticketsData);
      setAnalytics(analyticsData);
      setCalls(callsData);
    } catch (err) {
      console.warn("Backend connection issue:", err);
      setBackendError((err as Error).message || "Failed to connect to FastAPI backend");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Audio alert toggle
  const toggleSound = () => {
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    soundManager.enabled = !nextMuted;
    if (!nextMuted) {
      soundManager.playSuccessChime();
    }
  };

  // Ticket status progression
  const handleUpdateStatus = async (ticketId: number, nextStatus: TicketStatus) => {
    try {
      const updated = await updateTicket(ticketId, { status: nextStatus });
      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket && selectedTicket.id === ticketId) {
        setSelectedTicket(updated);
      }
      showToast(`Ticket #${ticketId} advanced to ${nextStatus.replace(/_/g, ' ')}`);
      soundManager.playSuccessChime();
      fetchAnalytics().then(setAnalytics).catch(() => {});
    } catch (err) {
      alert("Failed to advance status: " + (err as Error).message);
    }
  };

  // Phase 5 Lifecycle Handlers
  const handleAcknowledge = async (ticketId: number, staffName: string = 'Nurse on Duty') => {
    try {
      const updated = await acknowledgeTicket(ticketId, staffName);
      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket && selectedTicket.id === ticketId) {
        setSelectedTicket(updated);
      }
      showToast(`Ticket #${ticketId} acknowledged by ${staffName}`);
      soundManager.playSuccessChime();
      fetchAnalytics().then(setAnalytics).catch(() => {});
    } catch (err) {
      alert("Failed to acknowledge ticket: " + (err as Error).message);
    }
  };

  const handleAssign = async (ticketId: number, staff: string, team: string) => {
    try {
      const updated = await assignTicket(ticketId, {
        assigned_staff: staff,
        assigned_team: team
      });
      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket && selectedTicket.id === ticketId) {
        setSelectedTicket(updated);
      }
      showToast(`Ticket #${ticketId} assigned to ${staff || team}`);
      soundManager.playSuccessChime();
    } catch (err) {
      alert("Failed to assign ticket: " + (err as Error).message);
    }
  };

  const handleEscalate = async (ticketId: number, reason: string, staff: string) => {
    try {
      const updated = await escalateTicket(ticketId, reason, staff);
      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket && selectedTicket.id === ticketId) {
        setSelectedTicket(updated);
      }
      showToast(`Ticket #${ticketId} escalated to Level ${updated.escalation_level}`);
      soundManager.playEmergencyAlert();
      fetchAnalytics().then(setAnalytics).catch(() => {});
    } catch (err) {
      alert("Failed to escalate ticket: " + (err as Error).message);
    }
  };

  const handleResolve = async (ticketId: number, notes: string, staff: string) => {
    try {
      const updated = await resolveTicket(ticketId, notes, staff);
      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket && selectedTicket.id === ticketId) {
        setSelectedTicket(updated);
      }
      showToast(`Ticket #${ticketId} resolved by ${staff}`);
      soundManager.playSuccessChime();
      fetchAnalytics().then(setAnalytics).catch(() => {});
    } catch (err) {
      alert("Failed to resolve ticket: " + (err as Error).message);
    }
  };

  // Phase 6: Human Clinical Review & Audit Correction Handler
  const handleReviewTicket = async (ticketId: number, reviewData: any) => {
    try {
      const updated = await reviewTicket(ticketId, reviewData);
      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket && selectedTicket.id === ticketId) {
        setSelectedTicket(updated);
      }
      showToast(
        (reviewData.action === 'APPROVE' || reviewData.decision === 'APPROVE')
          ? `Ticket #${ticketId} clinically approved.`
          : `Ticket #${ticketId} corrected & SLA recalculated.`
      );
      soundManager.playSuccessChime();
      fetchAnalytics().then(setAnalytics).catch(() => {});
    } catch (err) {
      alert("Failed to review ticket: " + (err as Error).message);
    }
  };

  // Add clinical staff note
  const handleAddNote = async (ticketId: number, note: string, author: string) => {
    const updated = await addTicketNote(ticketId, note, author);
    setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
    setSelectedTicket(updated);
    showToast("Clinical triage note logged successfully");
    soundManager.playSuccessChime();
  };

  // Delete resolved ticket from backend and update dashboard state immediately
  const handleDeleteTicket = async (ticketId: number) => {
    try {
      await deleteTicket(ticketId);
      setTickets((prev) => prev.filter((t) => t.id !== ticketId));
      if (selectedTicket && selectedTicket.id === ticketId) {
        setSelectedTicket(null);
      }
      showToast(`Resolved ticket #${ticketId} deleted successfully.`);
      soundManager.playSuccessChime();
      fetchAnalytics().then(setAnalytics).catch(() => {});
    } catch (err) {
      alert("Failed to delete ticket: " + (err as Error).message);
    }
  };

  // Callback when audio is successfully transcribed & processed
  const handleAudioSuccess = (result: ProcessCallResult) => {
    showToast(
      `Call processed! Generated ${result.extracted_tickets.length} separate department tasks.`
    );
    loadDashboardData();
  };

  // Active STAT emergency tickets
  const activeEmergencyTickets = tickets.filter(
    (t) => t.urgency === 'STAT_EMERGENCY' && t.status !== 'RESOLVED'
  );

  const overdueTickets = tickets.filter((t) => t.is_overdue);
  const escalatedTickets = tickets.filter((t) => t.escalation_level && t.escalation_level > 0);
  const unreviewedTickets = tickets.filter((t) => t.requires_human_review && !t.is_reviewed);

  return (
    <div className="min-h-screen flex flex-col bg-[#060b13] text-slate-100 font-sans selection:bg-sky-500 selection:text-white">
      
      {/* Top Navigation Bar */}
      <Navbar
        activeTab={activeTab}
        onSelectTab={(tab) => {
          if (tab === 'analytics') {
            setIsAnalyticsOpen(true);
          } else {
            setActiveTab(tab);
          }
        }}
        isMuted={isMuted}
        onToggleSound={toggleSound}
        emergencyCount={activeEmergencyTickets.length}
        unreviewedCount={unreviewedTickets.length}
        callsCount={calls.length}
        onOpenShiftHandover={() => setIsShiftHandoverOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        
        {/* Backend Connection Error Banner */}
        {backendError && (
          <div className="p-4 rounded-xl bg-rose-950/70 border border-rose-500/50 text-rose-200 text-xs flex items-center justify-between gap-3 shadow-lg">
            <div className="flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-rose-400 shrink-0" />
              <span><strong>Backend Connectivity Warning:</strong> {backendError}. Ensure FastAPI is running on port 8000.</span>
            </div>
            <button
              onClick={() => {
                setIsLoading(true);
                loadDashboardData();
              }}
              className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shrink-0 transition-colors"
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* Toast Alert Banner */}
        {toastMessage && (
          <div className="p-3 rounded-xl bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 text-xs font-semibold flex items-center justify-between shadow-lg shadow-emerald-950/40 animate-slide-up">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>{toastMessage}</span>
            </div>
            <button
              onClick={() => setToastMessage(null)}
              className="text-emerald-400/80 hover:text-white"
            >
              &times;
            </button>
          </div>
        )}

        {/* View 1: Call Transcripts & Structured Summaries Explorer */}
        {activeTab === 'calls' ? (
          <div className="space-y-4 animate-fade-in">
            <div className="flex items-center justify-between pb-2">
              <button
                onClick={() => setActiveTab('board')}
                className="text-xs text-sky-400 hover:text-sky-300 font-semibold flex items-center gap-1.5 transition-colors"
              >
                &larr; Back to Live Triage Board
              </button>
            </div>
            <CallsExplorer
              onSelectTicket={(ticket) => setSelectedTicket(ticket)}
              onNavigateToRecord={() => setActiveTab('record')}
            />
          </div>
        ) : activeTab === 'record' ? (
          /* View 2: Audio Recorder & Call Intake */
          <div className="space-y-4 animate-fade-in">
            <div className="flex items-center justify-between pb-2">
              <button
                onClick={() => setActiveTab('board')}
                className="text-xs text-sky-400 hover:text-sky-300 font-semibold flex items-center gap-1.5 transition-colors"
              >
                &larr; Back to Live Triage Board
              </button>
            </div>
            <AudioRecorder
              onSuccess={handleAudioSuccess}
              onNavigateToBoard={() => setActiveTab('board')}
            />
          </div>
        ) : (
          /* View 2: Hospital Command Center & Triage Board */
          <div className="space-y-6 animate-fade-in">
            
            {/* STAT Emergency Alert Banner */}
            <EmergencyBanner
              emergencyTickets={activeEmergencyTickets}
              onSelectTicket={(t) => setSelectedTicket(t)}
            />

            {/* Hospital Command Center Metrics Header */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4">
              
              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-lg flex items-center space-x-3.5">
                <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 shrink-0">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Active Tasks
                  </span>
                  <span className="text-xl sm:text-2xl font-extrabold text-white">
                    {tickets.length}
                  </span>
                  <span className="text-[10px] text-slate-500 block">Across 6 departments</span>
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-lg flex items-center space-x-3.5">
                <div className={`p-2.5 rounded-xl border shrink-0 ${
                  activeEmergencyTickets.length > 0
                    ? 'bg-red-500/10 border-red-500/30 text-red-400 animate-pulse'
                    : 'bg-slate-800/60 border-slate-700 text-slate-400'
                }`}>
                  <AlertOctagon className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    STAT Response
                  </span>
                  <span className={`text-xl sm:text-2xl font-extrabold ${
                    activeEmergencyTickets.length > 0 ? 'text-red-400' : 'text-slate-300'
                  }`}>
                    {activeEmergencyTickets.length}
                  </span>
                  <span className="text-[10px] text-slate-500 block">Critical under 5m</span>
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-lg flex items-center space-x-3.5">
                <div className={`p-2.5 rounded-xl border shrink-0 ${
                  overdueTickets.length > 0
                    ? 'bg-red-500/10 border-red-500/30 text-red-400'
                    : 'bg-slate-800/60 border-slate-700 text-slate-400'
                }`}>
                  <Timer className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Overdue SLA
                  </span>
                  <span className={`text-xl sm:text-2xl font-extrabold ${
                    overdueTickets.length > 0 ? 'text-red-400' : 'text-slate-300'
                  }`}>
                    {overdueTickets.length}
                  </span>
                  <span className="text-[10px] text-slate-500 block">
                    {escalatedTickets.length > 0 ? `${escalatedTickets.length} escalated` : 'Target < 0'}
                  </span>
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-lg flex items-center space-x-3.5">
                <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0">
                  <Clock className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Pending Pickup
                  </span>
                  <span className="text-xl sm:text-2xl font-extrabold text-amber-300">
                    {tickets.filter((t) => t.status === 'PENDING').length}
                  </span>
                  <span className="text-[10px] text-slate-500 block">Awaiting triage</span>
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-lg flex items-center space-x-3.5">
                <div className="p-2.5 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-400 shrink-0">
                  <Activity className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Calls Ingested
                  </span>
                  <span className="text-xl sm:text-2xl font-extrabold text-teal-300">
                    {analytics?.total_calls || 0}
                  </span>
                  <span className="text-[10px] text-teal-400/80 block">Faster-Whisper STT</span>
                </div>
              </div>

            </div>

            {/* Quick Action Banner */}
            <div className="p-4 rounded-2xl bg-slate-900/40 border border-slate-800/90 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-sky-400 shrink-0" />
                <span className="text-xs font-bold text-slate-200">
                  Multilingual Clinical Voice Intake:
                </span>
                <span className="text-xs text-slate-400 hidden sm:inline">
                  Record real voice or upload audio in Kannada (ಕನ್ನಡ), Hindi (हिन्दी), or English
                </span>
              </div>

              <button
                onClick={() => setActiveTab('record')}
                id="board-quick-record-btn"
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-bold text-xs shadow-lg shadow-red-600/20 flex items-center gap-1.5 self-start sm:self-auto transition-all"
              >
                <Mic className="w-3.5 h-3.5" />
                <span>Record New Call</span>
              </button>
            </div>

            {/* Live Triage Board */}
            <TicketBoard
              tickets={tickets}
              onSelectTicket={(ticket) => setSelectedTicket(ticket)}
              onUpdateStatus={handleUpdateStatus}
              onDeleteTicket={handleDeleteTicket}
              onNavigateToRecord={() => setActiveTab('record')}
              onAcknowledge={(id) => handleAcknowledge(id, 'Nurse on Duty')}
            />

          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-[#060b13] py-4 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-400">CareRouter AI</span>
            <span>&bull;</span>
            <span>Multilingual Clinical Voice-to-Task Dispatch</span>
          </div>
          <div className="flex items-center space-x-3 text-[11px]">
            <span className="px-2 py-0.5 rounded bg-sky-950/60 border border-sky-800 text-sky-400">
              Faster-Whisper &bull; Kannada &bull; Hindi &bull; English
            </span>
            <span>FastAPI &bull; SQLite &bull; React TypeScript</span>
          </div>
        </div>
      </footer>

      {/* Ticket Details & Notes Modal */}
      <TicketDetailModal
        ticket={selectedTicket}
        onClose={() => setSelectedTicket(null)}
        onUpdateStatus={handleUpdateStatus}
        onAddNote={handleAddNote}
        onDelete={handleDeleteTicket}
        onAcknowledge={handleAcknowledge}
        onAssign={handleAssign}
        onEscalate={handleEscalate}
        onResolve={handleResolve}
        onReview={handleReviewTicket}
        onSelectSiblingTicket={(sib) => setSelectedTicket(sib)}
      />

      {/* Analytics Modal */}
      <AnalyticsModal
        isOpen={isAnalyticsOpen}
        onClose={() => setIsAnalyticsOpen(false)}
        analytics={analytics}
      />

      {/* Phase 6: Shift Handover & Hospital Reporting Modal */}
      <ShiftHandoverModal
        isOpen={isShiftHandoverOpen}
        onClose={() => setIsShiftHandoverOpen(false)}
      />

    </div>
  );
};

export default App;
