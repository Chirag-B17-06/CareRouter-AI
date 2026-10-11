import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchTickets,
  fetchScenarios,
  fetchAnalytics,
  processCall,
  updateTicket,
  addTicketNote,
  resetDemoDatabase
} from './services/api';
import { Ticket, Scenario, AnalyticsData, ProcessCallResult, TicketStatus } from './types';
import { Navbar } from './components/Navbar';
import { EmergencyBanner } from './components/EmergencyBanner';
import { TicketBoard } from './components/TicketBoard';
import { CallInputModal } from './components/CallInputModal';
import { TicketDetailModal } from './components/TicketDetailModal';
import { AnalyticsModal } from './components/AnalyticsModal';
import { DemoModeInfoModal } from './components/DemoModeInfoModal';
import { soundManager } from './utils/audio';
import {
  Activity,
  AlertOctagon,
  CheckCircle2,
  Clock,
  Layers,
  PhoneCall,
  Sparkles,
  ShieldAlert,
  HelpCircle
} from 'lucide-react';

export const App: React.FC = () => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Audio settings
  const [isMuted, setIsMuted] = useState<boolean>(false);

  // Modals state
  const [isCallModalOpen, setIsCallModalOpen] = useState<boolean>(false);
  const [isAnalyticsOpen, setIsAnalyticsOpen] = useState<boolean>(false);
  const [isInfoOpen, setIsInfoOpen] = useState<boolean>(false);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);

  // Notification toast
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Load all initial data from backend
  const loadDashboardData = useCallback(async () => {
    try {
      const [ticketsData, scenariosData, analyticsData] = await Promise.all([
        fetchTickets(),
        fetchScenarios(),
        fetchAnalytics()
      ]);
      setTickets(ticketsData);
      setScenarios(scenariosData);
      setAnalytics(analyticsData);
    } catch (err) {
      console.warn("Backend not ready or connection issue:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Audio mute toggle
  const toggleSound = () => {
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    soundManager.enabled = !nextMuted;
    if (!nextMuted) {
      soundManager.playSuccessChime();
    }
  };

  // Status progression
  const handleUpdateStatus = async (ticketId: number, nextStatus: TicketStatus) => {
    try {
      const updated = await updateTicket(ticketId, { status: nextStatus });
      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket && selectedTicket.id === ticketId) {
        setSelectedTicket(updated);
      }
      showToast(`Ticket #${ticketId} status advanced to ${nextStatus.replace(/_/g, ' ')}`);
      soundManager.playSuccessChime();
      // Refresh analytics in background
      fetchAnalytics().then(setAnalytics).catch(() => {});
    } catch (err) {
      alert("Failed to update status: " + (err as Error).message);
    }
  };

  // Add staff note
  const handleAddNote = async (ticketId: number, note: string, author: string) => {
    const updated = await addTicketNote(ticketId, note, author);
    setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
    setSelectedTicket(updated);
    showToast("Clinical note logged successfully");
    soundManager.playSuccessChime();
  };

  // Process incoming phone call
  const handleProcessCall = async (payload: {
    raw_transcript: string;
    caller_name?: string;
    caller_phone?: string;
    patient_name?: string;
    room_number?: string;
  }): Promise<ProcessCallResult> => {
    const result = await processCall(payload);
    await loadDashboardData();
    return result;
  };

  // Handle successful decomposition
  const handleDecompositionSuccess = (result: ProcessCallResult) => {
    showToast(
      `Call processed! ${result.extracted_tickets.length} new tasks dispatched across hospital departments.`
    );
    loadDashboardData();
  };

  // Reset database with initial scenarios
  const handleResetDb = async () => {
    if (!window.confirm("Reset triage board and seed initial 3 clinical scenarios?")) return;
    try {
      await resetDemoDatabase();
      await loadDashboardData();
      showToast("Triage board reset and re-seeded with demo scenarios.");
      soundManager.playSuccessChime();
    } catch (err) {
      alert("Failed to reset database: " + (err as Error).message);
    }
  };

  // Active STAT emergency tickets
  const activeEmergencyTickets = tickets.filter(
    (t) => t.urgency === 'STAT_EMERGENCY' && t.status !== 'RESOLVED'
  );

  return (
    <div className="min-h-screen flex flex-col bg-[#060b13] text-slate-100 font-sans selection:bg-sky-500 selection:text-white">
      
      {/* Top Navbar */}
      <Navbar
        onOpenCallModal={() => setIsCallModalOpen(true)}
        onOpenAnalytics={() => setIsAnalyticsOpen(true)}
        onOpenInfo={() => setIsInfoOpen(true)}
        onResetDb={handleResetDb}
        isMuted={isMuted}
        onToggleSound={toggleSound}
        emergencyCount={activeEmergencyTickets.length}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        
        {/* Toast Alert Banner */}
        {toastMessage && (
          <div className="p-3 rounded-xl bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 text-xs font-semibold flex items-center justify-between shadow-lg shadow-emerald-950/40 animate-slide-up">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>{toastMessage}</span>
            </div>
            <button onClick={() => setToastMessage(null)} className="text-emerald-400/80 hover:text-white">
              &times;
            </button>
          </div>
        )}

        {/* STAT Emergency Alert Banner */}
        <EmergencyBanner
          emergencyTickets={activeEmergencyTickets}
          onSelectTicket={(t) => setSelectedTicket(t)}
        />

        {/* Hospital Command Center Header Ribbon */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
          
          <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-lg flex items-center space-x-3.5">
            <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 shrink-0">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Total Tasks
              </span>
              <span className="text-xl sm:text-2xl font-extrabold text-white">
                {tickets.length}
              </span>
              <span className="text-[10px] text-slate-500 block">Active clinical tasks</span>
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
                STAT Rapid Response
              </span>
              <span className={`text-xl sm:text-2xl font-extrabold ${
                activeEmergencyTickets.length > 0 ? 'text-red-400' : 'text-slate-300'
              }`}>
                {activeEmergencyTickets.length}
              </span>
              <span className="text-[10px] text-slate-500 block">Critical SLA under 5m</span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-lg flex items-center space-x-3.5">
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Pending Triage
              </span>
              <span className="text-xl sm:text-2xl font-extrabold text-amber-300">
                {tickets.filter((t) => t.status === 'PENDING').length}
              </span>
              <span className="text-[10px] text-slate-500 block">Awaiting staff pickup</span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-lg flex items-center space-x-3.5">
            <div className="p-2.5 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-400 shrink-0">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                AI Decomposition
              </span>
              <span className="text-xl sm:text-2xl font-extrabold text-teal-300">
                100%
              </span>
              <span className="text-[10px] text-teal-400/80 block">Zero-Key NLP Engine</span>
            </div>
          </div>

        </div>

        {/* Quick Launch Demo Scenarios Bar */}
        <div className="p-4 rounded-2xl bg-slate-900/40 border border-slate-800/90 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-sky-400 shrink-0" />
            <span className="text-xs font-bold text-slate-200">
              Instant Demo Scenarios:
            </span>
            <span className="text-xs text-slate-400 hidden lg:inline">
              Simulate complex multi-request hospital calls in 1 click
            </span>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {scenarios.map((sc, index) => (
              <button
                key={sc.id}
                id={`quick-launch-${sc.id}-btn`}
                onClick={() => setIsCallModalOpen(true)}
                className="px-3 py-1.5 rounded-xl bg-slate-950 hover:bg-slate-800 border border-slate-800 text-xs font-medium text-slate-300 hover:text-white transition-colors flex items-center gap-1.5"
                title={sc.description}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
                <span>Scenario {index + 1}: {sc.room_number}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Main Ticket Board with Departments & Tasks */}
        <TicketBoard
          tickets={tickets}
          onSelectTicket={(ticket) => setSelectedTicket(ticket)}
          onUpdateStatus={handleUpdateStatus}
        />

      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-[#060b13] py-4 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-400">CareRouter AI</span>
            <span>&bull;</span>
            <span>Hospital Clinical Call-to-Task Dispatch System</span>
          </div>
          <div className="flex items-center space-x-3 text-[11px]">
            <span className="px-2 py-0.5 rounded bg-sky-950/60 border border-sky-800 text-sky-400">
              Demo Mode: Zero-Key Local NLP Active
            </span>
            <span>SQLite &bull; FastAPI &bull; React TypeScript</span>
          </div>
        </div>
      </footer>

      {/* Ingestion & AI Decomposition Modal */}
      <CallInputModal
        isOpen={isCallModalOpen}
        onClose={() => setIsCallModalOpen(false)}
        scenarios={scenarios}
        onProcessCall={handleProcessCall}
        onSuccess={handleDecompositionSuccess}
      />

      {/* Ticket Details & Notes Modal */}
      <TicketDetailModal
        ticket={selectedTicket}
        onClose={() => setSelectedTicket(null)}
        onUpdateStatus={handleUpdateStatus}
        onAddNote={handleAddNote}
      />

      {/* Analytics Modal */}
      <AnalyticsModal
        isOpen={isAnalyticsOpen}
        onClose={() => setIsAnalyticsOpen(false)}
        analytics={analytics}
      />

      {/* Zero-Key Demo Architecture Modal */}
      <DemoModeInfoModal
        isOpen={isInfoOpen}
        onClose={() => setIsInfoOpen(false)}
      />

    </div>
  );
};
export default App;
