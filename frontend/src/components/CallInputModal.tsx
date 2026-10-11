import React, { useState, useEffect } from 'react';
import {
  X,
  PhoneCall,
  Play,
  Square,
  Sparkles,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Radio,
  FileText,
  User,
  Bed,
  Phone
} from 'lucide-react';
import { Scenario, ProcessCallResult, Ticket } from '../types';
import { soundManager } from '../utils/audio';

interface CallInputModalProps {
  isOpen: boolean;
  onClose: () => void;
  scenarios: Scenario[];
  onProcessCall: (payload: {
    raw_transcript: string;
    caller_name?: string;
    caller_phone?: string;
    patient_name?: string;
    room_number?: string;
  }) => Promise<ProcessCallResult>;
  onSuccess: (result: ProcessCallResult) => void;
}

export const CallInputModal: React.FC<CallInputModalProps> = ({
  isOpen,
  onClose,
  scenarios,
  onProcessCall,
  onSuccess
}) => {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('scenario-1');
  const [callerName, setCallerName] = useState<string>('');
  const [callerPhone, setCallerPhone] = useState<string>('');
  const [patientName, setPatientName] = useState<string>('');
  const [roomNumber, setRoomNumber] = useState<string>('');
  const [transcript, setTranscript] = useState<string>('');

  // Audio simulation state
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);
  const [audioProgress, setAudioProgress] = useState<number>(0);

  // Processing state
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processStep, setProcessStep] = useState<number>(0);
  const [decompositionResult, setDecompositionResult] = useState<ProcessCallResult | null>(null);

  // Load selected scenario
  useEffect(() => {
    const sc = scenarios.find((s) => s.id === selectedScenarioId);
    if (sc) {
      setCallerName(sc.caller_name);
      setCallerPhone('+1 (555) 019-4821');
      setPatientName(sc.patient_name);
      setRoomNumber(sc.room_number);
      setTranscript(sc.transcript);
      setDecompositionResult(null);
    }
  }, [selectedScenarioId, scenarios]);

  // Handle Audio playback simulation
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (isPlayingAudio) {
      interval = setInterval(() => {
        setAudioProgress((prev) => {
          if (prev >= 100) {
            setIsPlayingAudio(false);
            return 0;
          }
          return prev + 5;
        });
      }, 300);
    } else {
      setAudioProgress(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlayingAudio]);

  const toggleAudioSimulation = () => {
    if (isPlayingAudio) {
      setIsPlayingAudio(false);
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    } else {
      setIsPlayingAudio(true);
      // Play a quick chime and use Web Speech API if supported
      soundManager.playSuccessChime();
      if (typeof window !== 'undefined' && 'speechSynthesis' in window && transcript) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(transcript);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;
        utterance.onend = () => setIsPlayingAudio(false);
        utterance.onerror = () => setIsPlayingAudio(false);
        window.speechSynthesis.speak(utterance);
      }
    }
  };

  const handleRunDecomposition = async () => {
    if (!transcript.trim()) return;
    setIsProcessing(true);
    setProcessStep(1);

    // Multi-phase animation for clear visual explanation to user/judges
    setTimeout(() => setProcessStep(2), 350);
    setTimeout(() => setProcessStep(3), 700);

    try {
      const result = await onProcessCall({
        raw_transcript: transcript,
        caller_name: callerName,
        caller_phone: callerPhone,
        patient_name: patientName,
        room_number: roomNumber
      });

      setProcessStep(4);
      setDecompositionResult(result);
      if (result.emergency_detected) {
        soundManager.playEmergencyAlert();
      } else {
        soundManager.playSuccessChime();
      }
    } catch (err) {
      console.error(err);
      alert('Error decomposing call: ' + (err as Error).message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleApplyAndClose = () => {
    if (decompositionResult) {
      onSuccess(decompositionResult);
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6 animate-fade-in">
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/70">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400">
              <PhoneCall className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                Incoming Call Intake &amp; AI Decomposition
                <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30 font-semibold">
                  Local Zero-Key
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Transform rambled clinical phone calls into separate, routed department tickets.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            id="close-call-modal-btn"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="overflow-y-auto p-4 sm:p-6 space-y-5 flex-1">
          
          {/* Step 1: Scenario Selector */}
          <div>
            <label className="text-xs font-bold text-slate-300 uppercase tracking-wider block mb-2">
              1. Choose a Working Demo Scenario (or Enter Custom Conversation Below)
            </label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
              {scenarios.map((sc) => {
                const isSelected = selectedScenarioId === sc.id;
                const isStat = sc.urgency_tier === 'STAT_EMERGENCY';
                return (
                  <button
                    key={sc.id}
                    id={`select-${sc.id}-btn`}
                    onClick={() => {
                      setSelectedScenarioId(sc.id);
                      setIsPlayingAudio(false);
                      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
                        window.speechSynthesis.cancel();
                      }
                    }}
                    className={`text-left p-3 rounded-xl border transition-all relative ${
                      isSelected
                        ? isStat
                          ? 'border-red-500/80 bg-red-950/30 ring-1 ring-red-500/40 shadow-lg'
                          : 'border-sky-500/80 bg-sky-950/30 ring-1 ring-sky-500/40 shadow-lg'
                        : 'border-slate-800 bg-slate-950/40 hover:bg-slate-800/40 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-white">{sc.room_number}</span>
                      <span
                        className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                          isStat
                            ? 'bg-red-500/20 text-red-300 border border-red-500/40'
                            : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        }`}
                      >
                        {isStat ? 'STAT CRITICAL' : 'URGENT'}
                      </span>
                    </div>
                    <div className="text-xs font-medium text-slate-200 line-clamp-1">{sc.patient_name}</div>
                    <div className="text-[11px] text-slate-400 line-clamp-2 mt-1 leading-snug">
                      {sc.description}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Caller & Patient Metadata Fields */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <div>
              <label className="text-[11px] font-medium text-slate-400 block mb-1 flex items-center gap-1">
                <User className="w-3 h-3 text-slate-500" /> Caller Name
              </label>
              <input
                type="text"
                value={callerName}
                onChange={(e) => setCallerName(e.target.value)}
                placeholder="e.g. Sarah Pendelton"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-400 block mb-1 flex items-center gap-1">
                <Phone className="w-3 h-3 text-slate-500" /> Phone
              </label>
              <input
                type="text"
                value={callerPhone}
                onChange={(e) => setCallerPhone(e.target.value)}
                placeholder="+1 (555) 019-4821"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-400 block mb-1 flex items-center gap-1">
                <Bed className="w-3 h-3 text-slate-500" /> Patient Name
              </label>
              <input
                type="text"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                placeholder="e.g. Arthur Pendelton"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-400 block mb-1 flex items-center gap-1">
                <Radio className="w-3 h-3 text-slate-500" /> Room / Bed
              </label>
              <input
                type="text"
                value={roomNumber}
                onChange={(e) => setRoomNumber(e.target.value)}
                placeholder="e.g. Room 314"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>

          {/* Audio Simulator Bar */}
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between gap-3">
            <div className="flex items-center space-x-3">
              <button
                type="button"
                id="toggle-call-audio-simulation-btn"
                onClick={toggleAudioSimulation}
                className={`p-2 rounded-lg font-medium text-xs flex items-center gap-1.5 transition-colors ${
                  isPlayingAudio
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    : 'bg-slate-800 hover:bg-slate-700 text-slate-200'
                }`}
              >
                {isPlayingAudio ? (
                  <>
                    <Square className="w-3.5 h-3.5 fill-current" />
                    <span>Stop Audio</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Play Audio Simulation</span>
                  </>
                )}
              </button>

              {/* Animated Equalizer Waveform */}
              <div className="flex items-center space-x-1 h-5">
                {[40, 70, 30, 90, 60, 80, 50, 95, 35, 75].map((height, i) => (
                  <div
                    key={i}
                    className={`w-1 rounded-full transition-all duration-200 ${
                      isPlayingAudio ? 'bg-sky-400 animate-pulse' : 'bg-slate-700'
                    }`}
                    style={{
                      height: isPlayingAudio ? `${height}%` : '20%',
                      animationDelay: `${i * 100}ms`
                    }}
                  />
                ))}
              </div>
            </div>

            <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
              <span>Hospital Call Audio Line: Active</span>
            </div>
          </div>

          {/* Transcript Textarea */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-sky-400" />
                Raw Phone Call Transcript
              </label>
              <span className="text-[11px] text-slate-500">
                Notice multiple unseparated clinical requests in a single speech stream
              </span>
            </div>
            <textarea
              rows={4}
              value={transcript}
              onChange={(e) => {
                setTranscript(e.target.value);
                setDecompositionResult(null);
              }}
              placeholder="Paste hospital conversation here..."
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-sky-500 font-mono leading-relaxed resize-none"
            />
          </div>

          {/* Process Button & Animation */}
          <div>
            <button
              onClick={handleRunDecomposition}
              disabled={isProcessing || !transcript.trim()}
              id="run-decomposition-btn"
              className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-sky-500 via-blue-600 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-bold text-sm shadow-xl shadow-sky-500/20 disabled:opacity-50 transition-all flex items-center justify-center space-x-2"
            >
              <Sparkles className="w-4 h-4 animate-spin-slow" />
              <span>
                {isProcessing
                  ? 'Decomposing Hospital Call with AI...'
                  : 'Process Call with CareRouter AI Engine'}
              </span>
            </button>

            {/* Stepper Status while processing */}
            {isProcessing && (
              <div className="mt-3 p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1.5 text-xs text-slate-300">
                <div className="flex items-center space-x-2">
                  <span className={`w-2 h-2 rounded-full ${processStep >= 1 ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                  <span>1. Parsing speaker transcript &amp; clinical entities...</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`w-2 h-2 rounded-full ${processStep >= 2 ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                  <span>2. Evaluating triage urgency &amp; STAT risk patterns...</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`w-2 h-2 rounded-full ${processStep >= 3 ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                  <span>3. Decomposing compound clauses into atomic tasks...</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`w-2 h-2 rounded-full ${processStep >= 4 ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                  <span>4. Assigning department destinations &amp; role dispatch...</span>
                </div>
              </div>
            )}
          </div>

          {/* Decomposition Result Preview */}
          {decompositionResult && (
            <div className="mt-4 p-4 rounded-xl bg-slate-950/90 border border-emerald-500/40 space-y-3 animate-slide-up">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span className="text-sm font-bold text-white">
                    Extraction Successful: {decompositionResult.extracted_tickets.length} Atomic Tasks Created
                  </span>
                </div>
                {decompositionResult.emergency_detected && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-red-600 text-white animate-pulse">
                    STAT EMERGENCY DETECTED
                  </span>
                )}
              </div>

              <p className="text-xs text-slate-300">
                {decompositionResult.summary}
              </p>

              {/* Render the separated tickets */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 pt-2">
                {decompositionResult.extracted_tickets.map((t: Ticket, idx: number) => {
                  const isStat = t.urgency === 'STAT_EMERGENCY';
                  return (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg border text-xs flex flex-col justify-between ${
                        isStat
                          ? 'border-red-500/50 bg-red-950/30'
                          : 'border-slate-800 bg-slate-900/60'
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] font-bold text-sky-400">{t.department}</span>
                          <span
                            className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                              isStat ? 'bg-red-500/20 text-red-300' : 'bg-slate-800 text-slate-300'
                            }`}
                          >
                            {t.urgency}
                          </span>
                        </div>
                        <h4 className="font-semibold text-white line-clamp-1">{t.title}</h4>
                        <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 italic">
                          &ldquo;{t.raw_quote}&rdquo;
                        </p>
                      </div>
                      <div className="mt-2 pt-2 border-t border-slate-800 text-[10px] text-slate-500">
                        Assigned: {t.assigned_to}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={handleApplyAndClose}
                  id="confirm-dispatch-tickets-btn"
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-md shadow-emerald-600/30 flex items-center space-x-1.5"
                >
                  <span>Apply &amp; View in Hospital Command Board</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

        </div>

      </div>
    </div>
  );
};
