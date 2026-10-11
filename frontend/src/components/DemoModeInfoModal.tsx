import React from 'react';
import {
  X,
  Sparkles,
  ShieldCheck,
  Cpu,
  Key,
  Layers,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';

interface DemoModeInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DemoModeInfoModal: React.FC<DemoModeInfoModalProps> = ({
  isOpen,
  onClose
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6 animate-fade-in">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">
                CareRouter AI: Zero-Key Demo Architecture
              </h2>
              <p className="text-xs text-slate-400">
                100% Offline, Deterministic Clinical NLP Engine
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            id="close-demo-info-modal-btn"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 text-xs text-slate-300 leading-relaxed overflow-y-auto max-h-[75vh]">
          
          <div className="p-3.5 rounded-xl bg-sky-950/30 border border-sky-500/30 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold text-sky-300 text-sm">
              <ShieldCheck className="w-4 h-4 text-sky-400" />
              <span>Hackathon Ready &bull; Zero External API Keys Required</span>
            </div>
            <p className="text-slate-300 text-[11px]">
              You can evaluate all features out-of-the-box. CareRouter AI embeds a specialized clinical heuristic NLP engine that decomposes multi-request phone calls without incurring API fees, rate limits, or network latency.
            </p>
          </div>

          <div className="space-y-3">
            <h4 className="font-bold text-white text-xs uppercase tracking-wider flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-teal-400" />
              How the Multi-Request NLP Engine Works:
            </h4>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                <span className="font-bold text-slate-200 block text-xs">1. Syntactic Clause Splitting</span>
                <p className="text-[11px] text-slate-400">
                  Splits compound phone conversations into atomic requests using clinical conjunctions (&ldquo;also&rdquo;, &ldquo;and one more thing&rdquo;, &ldquo;plus&rdquo;).
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                <span className="font-bold text-slate-200 block text-xs">2. STAT Threat Classification</span>
                <p className="text-[11px] text-slate-400">
                  Detects acute medical risks (swollen IV, active fall risk, unmanaged 8/10 pain) and routes to STAT Emergency with immediate alarm bells.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                <span className="font-bold text-slate-200 block text-xs">3. Department &amp; Role Dispatch</span>
                <p className="text-[11px] text-slate-400">
                  Routes tasks to Rapid Response, Nursing, Pharmacy, Dietary, Facilities, and Admin with automatic role assignment.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                <span className="font-bold text-slate-200 block text-xs">4. Clinical Safety Tagging</span>
                <p className="text-[11px] text-slate-400">
                  Attaches flags like <code className="text-amber-400">[IV_INFILTRATION]</code> and <code className="text-amber-400">[FALL_RISK]</code> to prevent medical oversights.
                </p>
              </div>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
            <h4 className="font-bold text-white text-xs uppercase tracking-wider flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-purple-400" />
              Optional External LLM Integration
            </h4>
            <p className="text-[11px] text-slate-400">
              If desired, you can add an <code className="text-sky-300">OPENAI_API_KEY</code> or <code className="text-sky-300">GROQ_API_KEY</code> to the <code className="text-slate-200">backend/.env</code> file. The backend will seamlessly detect it while keeping your keys secure and private.
            </p>
          </div>

        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs"
          >
            Got it, Let&apos;s Triage
          </button>
        </div>

      </div>
    </div>
  );
};
