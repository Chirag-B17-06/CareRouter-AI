import React, { useState, useRef, useEffect } from 'react';
import {
  Mic,
  MicOff,
  Square,
  Pause,
  Play,
  RotateCcw,
  Upload,
  FileAudio,
  CheckCircle2,
  AlertTriangle,
  Languages,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  Edit3,
  Clock,
  User,
  Bed,
  Phone,
  Trash2,
  Activity
} from 'lucide-react';
import { uploadAndTranscribeAudio, processTranscript } from '../services/api';
import { AudioTranscribeResult, ProcessCallResult, Ticket } from '../types';
import { soundManager } from '../utils/audio';

interface AudioRecorderProps {
  onSuccess: (result: ProcessCallResult) => void;
  onNavigateToBoard: () => void;
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({
  onSuccess,
  onNavigateToBoard
}) => {
  // Input Mode: 'record' | 'upload'
  const [activeTab, setActiveTab] = useState<'record' | 'upload'>('record');

  // Language Selection
  const [selectedLanguage, setSelectedLanguage] = useState<string>('auto');

  // Caller & Patient details
  const [callerName, setCallerName] = useState<string>('');
  const [callerPhone, setCallerPhone] = useState<string>('');
  const [patientName, setPatientName] = useState<string>('');
  const [roomNumber, setRoomNumber] = useState<string>('');

  // MediaRecorder states
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);
  const [recordedAudioBlob, setRecordedAudioBlob] = useState<Blob | null>(null);
  const [recordedAudioUrl, setRecordedAudioUrl] = useState<string | null>(null);
  const [micError, setMicError] = useState<string | null>(null);

  // File Upload states
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Transcription & Review states
  const [isTranscribing, setIsTranscribing] = useState<boolean>(false);
  const [transcribeResult, setTranscribeResult] = useState<AudioTranscribeResult | null>(null);
  const [editableTranscript, setEditableTranscript] = useState<string>('');

  // Ticket processing states
  const [isProcessingTickets, setIsProcessingTickets] = useState<boolean>(false);
  const [dispatchResult, setDispatchResult] = useState<ProcessCallResult | null>(null);

  // References
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  // Clean up recording URL on unmount
  useEffect(() => {
    return () => {
      if (recordedAudioUrl) {
        URL.revokeObjectURL(recordedAudioUrl);
      }
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, [recordedAudioUrl]);

  // Start Real Microphone Recording
  const startRecording = async () => {
    setMicError(null);
    setRecordedAudioBlob(null);
    if (recordedAudioUrl) {
      URL.revokeObjectURL(recordedAudioUrl);
      setRecordedAudioUrl(null);
    }
    setTranscribeResult(null);
    setDispatchResult(null);
    audioChunksRef.current = [];

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Your browser does not support microphone recording (MediaRecorder API).");
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      // Determine supported mime type
      const mimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/wav'];
      let selectedMime = '';
      for (const mime of mimeTypes) {
        if (MediaRecorder.isTypeSupported(mime)) {
          selectedMime = mime;
          break;
        }
      }

      const recorder = new MediaRecorder(stream, selectedMime ? { mimeType: selectedMime } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const mimeType = recorder.mimeType || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        setRecordedAudioBlob(blob);
        const url = URL.createObjectURL(blob);
        setRecordedAudioUrl(url);

        // Stop all audio tracks to turn off the microphone hardware light
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start(250); // Slice data every 250ms
      setIsRecording(true);
      setIsPaused(false);
      setRecordingSeconds(0);

      // Start elapsed timer
      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);

    } catch (err: unknown) {
      console.error("Microphone access error:", err);
      const errMsg = (err as Error).name === 'NotAllowedError'
        ? "Microphone permission denied. Please click the lock icon in your browser address bar and allow microphone access."
        : `Could not access microphone: ${(err as Error).message}`;
      setMicError(errMsg);
    }
  };

  // Pause Recording
  const pauseRecording = () => {
    if (mediaRecorderRef.current && isRecording && !isPaused) {
      mediaRecorderRef.current.pause();
      setIsPaused(true);
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    }
  };

  // Resume Recording
  const resumeRecording = () => {
    if (mediaRecorderRef.current && isRecording && isPaused) {
      mediaRecorderRef.current.resume();
      setIsPaused(false);
      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    }
  };

  // Stop Recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsPaused(false);
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
      soundManager.playSuccessChime();
    }
  };

  // Delete / Discard Recording
  const discardRecording = () => {
    if (recordedAudioUrl) {
      URL.revokeObjectURL(recordedAudioUrl);
    }
    setRecordedAudioBlob(null);
    setRecordedAudioUrl(null);
    setRecordingSeconds(0);
    setTranscribeResult(null);
    setEditableTranscript('');
    setDispatchResult(null);
  };

  // Handle Uploaded File
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUploadError(null);
    setTranscribeResult(null);
    setDispatchResult(null);
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const allowed = ['.webm', '.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac'];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!allowed.includes(ext)) {
      setUploadError(`Unsupported format '${ext}'. Supported formats: ${allowed.join(', ')}`);
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      setUploadError("File size exceeds 25 MB limit.");
      return;
    }

    setUploadedFile(file);
  };

  // Step 1: Submit Audio to faster-whisper Speech-to-Text
  const handleTranscribeAudio = async () => {
    const audioInput = activeTab === 'record' ? recordedAudioBlob : uploadedFile;
    if (!audioInput) {
      alert("Please record or select an audio file first.");
      return;
    }

    setIsTranscribing(true);
    try {
      const filename = activeTab === 'record' ? 'mic_recording.webm' : (uploadedFile?.name || 'uploaded_call.webm');
      const result = await uploadAndTranscribeAudio(audioInput, selectedLanguage, filename);
      setTranscribeResult(result);
      setEditableTranscript(result.transcript);
      soundManager.playSuccessChime();
    } catch (err: unknown) {
      console.error("Transcription error:", err);
      alert(`Transcription Failed: ${(err as Error).message}`);
    } finally {
      setIsTranscribing(false);
    }
  };

  // Step 2: Process the Reviewed Transcript into Clinical Tickets
  const handleProcessTickets = async () => {
    if (!editableTranscript.trim()) {
      alert("Please enter or verify the conversation transcript before processing.");
      return;
    }

    setIsProcessingTickets(true);
    try {
      const result = await processTranscript({
        raw_transcript: editableTranscript,
        language: transcribeResult?.language || (selectedLanguage !== 'auto' ? selectedLanguage : undefined),
        caller_name: callerName.trim() || undefined,
        caller_phone: callerPhone.trim() || undefined,
        patient_name: patientName.trim() || undefined,
        room_number: roomNumber.trim() || undefined,
        audio_filename: transcribeResult?.audio_filename
      });

      setDispatchResult(result);
      onSuccess(result);

      if (result.emergency_detected) {
        soundManager.playEmergencyAlert();
      } else {
        soundManager.playSuccessChime();
      }
    } catch (err: unknown) {
      console.error("Ticket processing error:", err);
      alert(`Error decomposing call into tasks: ${(err as Error).message}`);
    } finally {
      setIsProcessingTickets(false);
    }
  };

  // Formatting helper for mm:ss
  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      
      {/* Title & Medical Consent Notice */}
      <div className="p-4 sm:p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
              <Mic className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                Clinical Audio Call Recorder &amp; Intake
              </h2>
              <p className="text-xs text-slate-400">
                Record your voice or upload audio calls in Kannada (ಕನ್ನಡ), Hindi (हिन्दी), or English.
              </p>
            </div>
          </div>

          {/* Language Selector Dropdown */}
          <div className="flex items-center space-x-2 bg-slate-950 p-1.5 rounded-xl border border-slate-800">
            <Languages className="w-4 h-4 text-sky-400 ml-1.5" />
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              id="speech-language-select"
              aria-label="Speech recognition language"
              className="bg-transparent text-xs font-semibold text-slate-200 focus:outline-none cursor-pointer pr-2"
            >
              <option value="auto">🌐 Auto Detect Language</option>
              <option value="kn">ಕನ್ನಡ — Kannada</option>
              <option value="hi">हिन्दी — Hindi</option>
              <option value="en">English — English</option>
            </select>
          </div>
        </div>

        {/* Consent Notice */}
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-300 flex items-start gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <span>
            <strong>Patient Privacy &amp; Recording Consent:</strong> Obtain explicit consent before recording hospital conversations. Audio is processed for clinical triage and task dispatch. Decision support prototype only.
          </span>
        </div>
      </div>

      {/* Caller & Patient Information Fields */}
      <div className="p-4 sm:p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-3">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
          <User className="w-3.5 h-3.5 text-sky-400" />
          Call Intake Details (Optional or Auto-Extracted)
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div>
            <label className="text-[11px] font-medium text-slate-400 block mb-1">Caller Name</label>
            <input
              type="text"
              value={callerName}
              onChange={(e) => setCallerName(e.target.value)}
              placeholder="e.g. Sarah / ರಾಜೇಶ್"
              className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
            />
          </div>
          <div>
            <label className="text-[11px] font-medium text-slate-400 block mb-1">Phone Number</label>
            <input
              type="text"
              value={callerPhone}
              onChange={(e) => setCallerPhone(e.target.value)}
              placeholder="+91 98765 43210"
              className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
            />
          </div>
          <div>
            <label className="text-[11px] font-medium text-slate-400 block mb-1">Patient Name</label>
            <input
              type="text"
              value={patientName}
              onChange={(e) => setPatientName(e.target.value)}
              placeholder="e.g. Arthur / ರಮೇಶ್"
              className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
            />
          </div>
          <div>
            <label className="text-[11px] font-medium text-slate-400 block mb-1">Room / Bed #</label>
            <input
              type="text"
              value={roomNumber}
              onChange={(e) => setRoomNumber(e.target.value)}
              placeholder="e.g. Room 314 / ಕೋಣೆ 108"
              className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
            />
          </div>
        </div>
      </div>

      {/* Main Workstation: Record vs Upload Tabs */}
      <div className="p-5 sm:p-6 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl space-y-6">
        
        {/* Toggle Mode */}
        <div className="flex border-b border-slate-800 pb-3 gap-4">
          <button
            onClick={() => setActiveTab('record')}
            id="tab-microphone-record-btn"
            className={`pb-2 text-xs font-bold transition-all flex items-center gap-2 ${
              activeTab === 'record'
                ? 'text-sky-400 border-b-2 border-sky-400'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Mic className="w-4 h-4" />
            <span>Microphone Audio Recording</span>
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            id="tab-audio-upload-btn"
            className={`pb-2 text-xs font-bold transition-all flex items-center gap-2 ${
              activeTab === 'upload'
                ? 'text-sky-400 border-b-2 border-sky-400'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>Upload Audio File</span>
          </button>
        </div>

        {/* Tab 1: Microphone Recorder */}
        {activeTab === 'record' && (
          <div className="space-y-6">
            
            {/* Mic Error Banner */}
            {micError && (
              <div className="p-3 rounded-xl bg-red-950/60 border border-red-500/40 text-red-300 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <span>{micError}</span>
              </div>
            )}

            {/* Recording Visual Stage */}
            <div className="p-8 rounded-2xl bg-slate-950 border border-slate-800 flex flex-col items-center justify-center space-y-4 text-center relative overflow-hidden">
              
              {/* Background live pulse ring when recording */}
              {isRecording && !isPaused && (
                <div className="absolute inset-0 bg-red-500/5 animate-pulse pointer-events-none" />
              )}

              {/* Status pill & Timer */}
              <div className="flex items-center space-x-2">
                {isRecording ? (
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 ${
                    isPaused ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'bg-red-500/20 text-red-300 border border-red-500/40 animate-pulse'
                  }`}>
                    <span className={`w-2 h-2 rounded-full ${isPaused ? 'bg-amber-400' : 'bg-red-500 animate-ping'}`} />
                    {isPaused ? 'RECORDING PAUSED' : 'LIVE RECORDING'}
                  </span>
                ) : recordedAudioBlob ? (
                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    RECORDING READY FOR REVIEW
                  </span>
                ) : (
                  <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400">
                    STANDBY
                  </span>
                )}
              </div>

              {/* Time Counter */}
              <div className="text-4xl sm:text-5xl font-mono font-extrabold text-white tracking-widest">
                {formatTime(recordingSeconds)}
              </div>

              {/* Animated Waveform Visualizer */}
              <div className="flex items-center space-x-1.5 h-8">
                {[15, 45, 80, 30, 95, 60, 40, 75, 90, 50, 30, 70, 85, 40, 60].map((h, idx) => (
                  <div
                    key={idx}
                    className={`w-1 rounded-full transition-all duration-150 ${
                      isRecording && !isPaused ? 'bg-sky-400 animate-pulse' : 'bg-slate-800'
                    }`}
                    style={{
                      height: isRecording && !isPaused ? `${h}%` : '20%',
                      animationDelay: `${idx * 70}ms`
                    }}
                  />
                ))}
              </div>

              {/* Main Record Control Buttons */}
              <div className="flex items-center gap-3 pt-2">
                {!isRecording ? (
                  <button
                    onClick={startRecording}
                    id="start-mic-recording-btn"
                    className="px-6 py-3 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-bold text-sm shadow-xl shadow-red-600/30 flex items-center gap-2 active:scale-95 transition-all"
                  >
                    <Mic className="w-4 h-4 fill-current" />
                    <span>{recordedAudioBlob ? 'Record Again' : 'Start Recording'}</span>
                  </button>
                ) : (
                  <>
                    {isPaused ? (
                      <button
                        onClick={resumeRecording}
                        id="resume-recording-btn"
                        className="px-4 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs flex items-center gap-1.5"
                      >
                        <Play className="w-4 h-4 fill-current" />
                        <span>Resume</span>
                      </button>
                    ) : (
                      <button
                        onClick={pauseRecording}
                        id="pause-recording-btn"
                        className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs flex items-center gap-1.5 border border-slate-700"
                      >
                        <Pause className="w-4 h-4 fill-current" />
                        <span>Pause</span>
                      </button>
                    )}

                    <button
                      onClick={stopRecording}
                      id="stop-recording-btn"
                      className="px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-red-600/30"
                    >
                      <Square className="w-4 h-4 fill-current" />
                      <span>Stop Recording</span>
                    </button>
                  </>
                )}
              </div>

            </div>

            {/* Audio Playback & Actions After Stopping */}
            {recordedAudioUrl && !isRecording && (
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-fade-in">
                <div className="flex items-center space-x-3 flex-1">
                  <FileAudio className="w-6 h-6 text-sky-400 shrink-0" />
                  <div className="w-full max-w-md">
                    <audio
                      ref={audioPlayerRef}
                      src={recordedAudioUrl}
                      controls
                      className="w-full h-8"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={discardRecording}
                    id="discard-recording-btn"
                    className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-red-400 hover:bg-slate-800 transition-colors"
                    title="Discard recording"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleTranscribeAudio}
                    disabled={isTranscribing}
                    id="transcribe-recording-btn"
                    className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs shadow-md shadow-sky-600/30 flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>{isTranscribing ? 'Transcribing with Whisper...' : 'Transcribe Audio'}</span>
                  </button>
                </div>
              </div>
            )}

          </div>
        )}

        {/* Tab 2: Upload Audio File */}
        {activeTab === 'upload' && (
          <div className="space-y-4">
            
            {uploadError && (
              <div className="p-3 rounded-xl bg-red-950/60 border border-red-500/40 text-red-300 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <span>{uploadError}</span>
              </div>
            )}

            <div className="border-2 border-dashed border-slate-800 hover:border-sky-500/50 rounded-2xl p-8 text-center bg-slate-950/60 transition-all flex flex-col items-center justify-center space-y-3">
              <div className="p-3 rounded-full bg-slate-800/80 text-sky-400">
                <Upload className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">
                  {uploadedFile ? uploadedFile.name : 'Choose an audio file or drag & drop here'}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Supported formats: WebM, WAV, MP3, M4A, OGG, FLAC (Max 25 MB)
                </p>
              </div>

              <label
                htmlFor="file-upload-input"
                className="cursor-pointer px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs transition-colors"
              >
                Browse Audio File
              </label>
              <input
                id="file-upload-input"
                type="file"
                accept="audio/*,.webm,.wav,.mp3,.m4a,.ogg,.flac"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>

            {uploadedFile && (
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-2 text-xs text-slate-300">
                  <FileAudio className="w-4 h-4 text-sky-400" />
                  <span className="font-semibold">{uploadedFile.name}</span>
                  <span className="text-slate-500">({(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB)</span>
                </div>

                <button
                  onClick={handleTranscribeAudio}
                  disabled={isTranscribing}
                  id="transcribe-uploaded-file-btn"
                  className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs shadow-md shadow-sky-600/30 flex items-center gap-1.5 disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{isTranscribing ? 'Transcribing with Whisper...' : 'Transcribe Audio'}</span>
                </button>
              </div>
            )}

          </div>
        )}

        {/* Step 2: Transcript Review & Edit (Kannada, Hindi, English) */}
        {transcribeResult && (
          <div className="pt-4 border-t border-slate-800 space-y-4 animate-slide-up">
            
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <Edit3 className="w-4 h-4 text-sky-400" />
                <h3 className="text-sm font-bold text-white">
                  Step 2: Review &amp; Verify Transcript
                </h3>
              </div>

              {/* Language & Confidence Badge */}
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                  {transcribeResult.language_name}
                </span>
                <span className="text-[11px] text-slate-400">
                  Confidence: {Math.round(transcribeResult.transcription_confidence * 100)}%
                </span>
              </div>
            </div>

            <p className="text-xs text-slate-400">
              The speech was transcribed in its native script. You can review, correct medical terms or names, then click below to generate department tickets.
            </p>

            {/* Editable Textarea in Native Unicode Font */}
            <textarea
              rows={4}
              value={editableTranscript}
              onChange={(e) => setEditableTranscript(e.target.value)}
              placeholder="Speech transcript will appear here in Kannada, Hindi, or English..."
              className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-sky-500 font-sans leading-relaxed resize-none kannada-text hindi-text"
            />

            {/* Step 3: Trigger Multi-Request Decomposition */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-slate-500">
                Ready to extract separate clinical tasks &amp; route to hospital departments.
              </span>

              <button
                onClick={handleProcessTickets}
                disabled={isProcessingTickets || !editableTranscript.trim()}
                id="process-verified-transcript-btn"
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/30 flex items-center gap-2 disabled:opacity-50 transition-all"
              >
                <Activity className="w-4 h-4" />
                <span>{isProcessingTickets ? 'Analyzing Clinical Requests...' : 'Analyze & Dispatch Tickets'}</span>
              </button>
            </div>

          </div>
        )}

        {/* Step 3: Dispatch Outcome & Jump to Dashboard */}
        {dispatchResult && (
          <div className="p-4 rounded-xl bg-slate-950 border border-emerald-500/40 space-y-3 animate-slide-up">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span className="text-sm font-bold text-white">
                  Successfully Generated {dispatchResult.extracted_tickets.length} Hospital Department Tasks
                </span>
              </div>
              {dispatchResult.emergency_detected && (
                <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-red-600 text-white animate-pulse">
                  🚨 STAT EMERGENCY DETECTED
                </span>
              )}
            </div>

            <p className="text-xs text-slate-300">
              {dispatchResult.summary}
            </p>

            {/* Quick list of extracted tasks */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 pt-1">
              {dispatchResult.extracted_tickets.map((t: Ticket, idx: number) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg border text-xs ${
                    t.urgency === 'STAT_EMERGENCY'
                      ? 'border-red-500/50 bg-red-950/20'
                      : 'border-slate-800 bg-slate-900/60'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold text-sky-400">{t.department}</span>
                    <span className="text-[9px] font-bold text-slate-400 uppercase">{t.urgency.replace(/_/g, ' ')}</span>
                  </div>
                  <h4 className="font-semibold text-white line-clamp-1">{t.title}</h4>
                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 italic">
                    &ldquo;{t.raw_quote}&rdquo;
                  </p>
                </div>
              ))}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={onNavigateToBoard}
                id="view-in-triage-board-btn"
                className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs shadow-md shadow-sky-600/30 flex items-center gap-1.5"
              >
                <span>View All Tasks in Live Triage Board</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
