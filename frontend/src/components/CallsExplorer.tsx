import React, { useState, useEffect } from 'react';
import {
  Phone,
  User,
  Bed,
  Calendar,
  Languages,
  Clock,
  Sparkles,
  Layers,
  Search,
  Trash2,
  RefreshCw,
  FileText,
  Volume2,
  AlertOctagon,
  CheckCircle2,
  ArrowRight,
  ShieldAlert,
  Mic,
  AlertTriangle
} from 'lucide-react';
import { Call, Ticket } from '../types';
import { fetchCalls, deleteCall, getAudioFileUrl } from '../services/api';

interface CallsExplorerProps {
  onSelectTicket: (ticket: Ticket) => void;
  onNavigateToRecord: () => void;
}

export const CallsExplorer: React.FC<CallsExplorerProps> = ({
  onSelectTicket,
  onNavigateToRecord
}) => {
  const [calls, setCalls] = useState<Call[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedLanguage, setSelectedLanguage] = useState<string>('All');
  const [expandedCallId, setExpandedCallId] = useState<number | null>(null);

  const loadCalls = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchCalls();
      setCalls(data);
      if (data.length > 0 && expandedCallId === null) {
        setExpandedCallId(data[0].id);
      }
    } catch (err) {
      setError((err as Error).message || 'Failed to load call transcripts');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCalls();
  }, []);

  const handleDeleteCall = async (callId: number) => {
    if (!window.confirm(`Delete Call record #${callId} and all its associated department tasks?`)) {
      return;
    }
    try {
      await deleteCall(callId);
      setCalls((prev) => prev.filter((c) => c.id !== callId));
      if (expandedCallId === callId) {
        setExpandedCallId(null);
      }
    } catch (err) {
      alert('Failed to delete call: ' + (err as Error).message);
    }
  };

  const filteredCalls = calls.filter((c) => {
    if (selectedLanguage !== 'All' && c.language !== selectedLanguage) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const match =
        c.caller_name.toLowerCase().includes(q) ||
        c.caller_phone.toLowerCase().includes(q) ||
        c.patient_name.toLowerCase().includes(q) ||
        c.room_number.toLowerCase().includes(q) ||
        c.raw_transcript.toLowerCase().includes(q) ||
        c.summary.toLowerCase().includes(q) ||
        (c.translated_transcript && c.translated_transcript.toLowerCase().includes(q));
      if (!match) return false;
    }
    return true;
  });

  const getLanguageLabel = (lang?: string) => {
    if (lang === 'kn') return { label: 'ಕನ್ನಡ (Kannada)', class: 'kannada-text bg-purple-500/15 text-purple-300 border-purple-500/30' };
    if (lang === 'hi') return { label: 'हिन्दी (Hindi)', class: 'hindi-text bg-orange-500/15 text-orange-300 border-orange-500/30' };
    return { label: 'English', class: 'bg-sky-500/15 text-sky-300 border-sky-500/30' };
  };

  return (
    <div className="space-y-4 animate-fade-in">
      
      {/* Top Header & Search Controls */}
      <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
              <Phone className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>Call Transcripts &amp; Structured Summaries</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/40">
                  {calls.length} Ingested
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Auditable voice intake records, native language transcripts, AI summaries &amp; decomposed tasks
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Language filter */}
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              id="calls-language-filter"
              aria-label="Filter calls by language"
              className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500 cursor-pointer"
            >
              <option value="All">All Languages</option>
              <option value="kn">ಕನ್ನಡ (Kannada)</option>
              <option value="hi">हिन्दी (Hindi)</option>
              <option value="en">English</option>
            </select>

            <button
              onClick={loadCalls}
              disabled={isLoading}
              id="refresh-calls-btn"
              className="p-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-400 hover:text-white transition-colors disabled:opacity-50"
              title="Refresh Calls List"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            id="calls-search-input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search transcript text, caller name, room 314, summary keywords..."
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
          />
        </div>
      </div>

      {/* Main Content Area */}
      {isLoading && calls.length === 0 ? (
        /* Loading Skeleton State */
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse space-y-3">
              <div className="flex justify-between items-center">
                <div className="h-4 bg-slate-800 rounded w-1/4"></div>
                <div className="h-4 bg-slate-800 rounded w-1/6"></div>
              </div>
              <div className="h-16 bg-slate-950 rounded-xl"></div>
              <div className="h-10 bg-slate-800 rounded"></div>
            </div>
          ))}
        </div>
      ) : error ? (
        /* Error State */
        <div className="p-8 rounded-2xl bg-rose-950/40 border border-rose-500/50 text-center space-y-3">
          <AlertOctagon className="w-8 h-8 text-rose-400 mx-auto" />
          <h3 className="text-sm font-bold text-rose-200">Unable to Load Calls</h3>
          <p className="text-xs text-rose-300 max-w-md mx-auto">{error}</p>
          <button
            onClick={loadCalls}
            className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs shadow-md"
          >
            Retry Connection
          </button>
        </div>
      ) : calls.length === 0 ? (
        /* Empty State */
        <div className="p-12 text-center rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col items-center justify-center space-y-4">
          <div className="p-4 rounded-2xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <Mic className="w-10 h-10" />
          </div>
          <div className="max-w-md">
            <h3 className="text-lg font-bold text-white">No Call Transcripts Ingested</h3>
            <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
              Record conversations using your microphone or upload audio recordings in Kannada, Hindi, or English. CareRouter will transcribe the voice and synthesize structured clinical summaries.
            </p>
          </div>
          <button
            onClick={onNavigateToRecord}
            id="calls-explorer-record-btn"
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-bold text-xs shadow-lg shadow-red-600/20 flex items-center gap-2 active:scale-95 transition-all"
          >
            <Mic className="w-4 h-4" />
            <span>Record / Ingest First Call</span>
          </button>
        </div>
      ) : filteredCalls.length === 0 ? (
        /* Filtered Empty State */
        <div className="p-10 text-center rounded-2xl bg-slate-900/40 border border-slate-800 text-slate-400 text-xs">
          No calls match your search query &quot;{searchQuery}&quot;. Try adjusting your search or language filter.
        </div>
      ) : (
        /* Calls Feed */
        <div className="space-y-4">
          {filteredCalls.map((call) => {
            const isExpanded = expandedCallId === call.id;
            const langInfo = getLanguageLabel(call.language);
            const callTickets = call.tickets || [];
            const hasEmergency = callTickets.some((t) => t.urgency === 'STAT_EMERGENCY');

            return (
              <div
                key={call.id}
                className={`rounded-2xl border transition-all duration-200 overflow-hidden ${
                  hasEmergency
                    ? 'bg-red-950/20 border-red-500/40 shadow-lg'
                    : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
                }`}
              >
                {/* Call Summary Card Header */}
                <div
                  onClick={() => setExpandedCallId(isExpanded ? null : call.id)}
                  className="p-4 sm:p-5 cursor-pointer flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 hover:bg-slate-800/40 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-bold text-white flex items-center gap-1.5">
                        <Phone className="w-3.5 h-3.5 text-sky-400" />
                        <span>Call #{call.id}</span>
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${langInfo.class}`}>
                        {langInfo.label}
                      </span>
                      {hasEmergency && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-black bg-red-600 text-white animate-pulse">
                          STAT INCIDENT
                        </span>
                      )}
                      <span className="text-[11px] text-slate-400">
                        {new Date(call.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-slate-300 flex-wrap">
                      <span className="flex items-center gap-1">
                        <Bed className="w-3.5 h-3.5 text-sky-400" />
                        <strong>Room:</strong> {call.room_number || 'General Hospital'}
                      </span>
                      <span className="flex items-center gap-1">
                        <User className="w-3.5 h-3.5 text-slate-400" />
                        <strong>Patient:</strong> {call.patient_name || 'Inpatient'}
                      </span>
                      {call.caller_name && (
                        <span className="text-slate-400">
                          Caller: <strong className="text-slate-200">{call.caller_name}</strong> {call.caller_phone ? `(${call.caller_phone})` : ''}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center">
                    <span className="px-2.5 py-1 rounded-lg bg-sky-950/70 border border-sky-800/60 text-sky-300 text-xs font-semibold flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5" />
                      <span>{callTickets.length} Tasks Extracted</span>
                    </span>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteCall(call.id);
                      }}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-950/40 transition-colors"
                      title="Delete Call Record"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Collapsible Expanded Details */}
                {isExpanded && (
                  <div className="px-4 sm:px-5 pb-5 pt-1 border-t border-slate-800/80 space-y-4">
                    
                    {/* Audio Player if recording exists */}
                    {call.audio_filename && (
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center gap-2 text-xs text-slate-300">
                          <Volume2 className="w-4 h-4 text-sky-400 shrink-0" />
                          <span className="font-semibold">Original Voice Recording Audio:</span>
                          <span className="text-[10px] text-slate-500 font-mono truncate max-w-xs">{call.audio_filename}</span>
                        </div>
                        <audio
                          controls
                          src={getAudioFileUrl(call.audio_filename)}
                          className="h-8 max-w-full sm:max-w-xs"
                          preload="none"
                        />
                      </div>
                    )}

                    {/* AI Structured Clinical Summary */}
                    <div className="p-3.5 rounded-xl bg-slate-950 border border-sky-500/20 space-y-1.5">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-sky-300 uppercase tracking-wide">
                        <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                        <span>AI Structured Clinical Summary</span>
                      </div>
                      <p className="text-xs text-slate-200 leading-relaxed font-sans">
                        {call.summary || 'Summary generated from conversation breakdown.'}
                      </p>
                    </div>

                    {/* Raw Native Speech Transcript */}
                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span className="font-bold uppercase tracking-wider flex items-center gap-1.5 text-slate-300">
                          <FileText className="w-3.5 h-3.5 text-purple-400" />
                          <span>Full Ingested Speech Transcript ({langInfo.label})</span>
                        </span>
                        <span className="text-[10px] font-mono text-slate-500">
                          Confidence: {Math.round((call.language_confidence || 0.95) * 100)}%
                        </span>
                      </div>
                      <p className={`text-xs text-slate-100 p-3 rounded-lg bg-slate-900/80 border border-slate-800 leading-relaxed ${
                        call.language === 'kn' ? 'kannada-text text-sm' : call.language === 'hi' ? 'hindi-text text-sm' : ''
                      }`}>
                        &ldquo;{call.raw_transcript}&rdquo;
                      </p>

                      {call.translated_transcript && call.language !== 'en' && (
                        <div className="mt-2 pt-2 border-t border-slate-900 text-xs">
                          <span className="text-[10px] uppercase font-bold text-sky-400 block mb-0.5">
                            English Clinical Translation:
                          </span>
                          <p className="text-slate-300 text-xs italic">
                            &ldquo;{call.translated_transcript}&rdquo;
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Extracted Tasks from this Call */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-teal-400" />
                          <span>Separated Actionable Department Tasks ({callTickets.length})</span>
                        </h4>
                      </div>

                      {callTickets.length === 0 ? (
                        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-500 italic">
                          No distinct tasks extracted from this call.
                        </div>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                          {callTickets.map((t) => (
                            <div
                              key={t.id}
                              onClick={() => onSelectTicket(t)}
                              className="p-3 rounded-xl bg-slate-950/90 border border-slate-800 hover:border-sky-500/50 cursor-pointer transition-all flex flex-col justify-between space-y-2 group"
                            >
                              <div>
                                <div className="flex items-center justify-between gap-1 mb-1">
                                  <span className="text-[10px] font-bold text-sky-300 bg-sky-950/60 border border-sky-800/60 px-1.5 py-0.5 rounded truncate max-w-[150px]">
                                    {t.department}
                                  </span>
                                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border uppercase ${
                                    t.urgency === 'STAT_EMERGENCY'
                                      ? 'bg-red-600/20 text-red-300 border-red-500/50'
                                      : t.urgency === 'URGENT'
                                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                                      : 'bg-sky-500/15 text-sky-300 border-sky-500/30'
                                  }`}>
                                    {t.urgency.replace(/_/g, ' ')}
                                  </span>
                                </div>
                                <h5 className="text-xs font-semibold text-white group-hover:text-sky-300 transition-colors line-clamp-1">
                                  {t.title}
                                </h5>
                                {t.required_action && (
                                  <p className="text-[11px] text-slate-400 line-clamp-2 mt-0.5">
                                    {t.required_action}
                                  </p>
                                )}
                              </div>

                              <div className="flex items-center justify-between pt-1 border-t border-slate-900 text-[10px] text-slate-500">
                                <span>Status: <strong className="text-slate-300 uppercase">{t.status.replace(/_/g, ' ')}</strong></span>
                                <span className="text-sky-400 group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5 font-semibold">
                                  <span>Inspect</span>
                                  <ArrowRight className="w-2.5 h-2.5" />
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                  </div>
                )}

              </div>
            );
          })}
        </div>
      )}

    </div>
  );
};
