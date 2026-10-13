// Near-live transcript while the nurse is speaking.
//
// The browser only captures audio; all speech recognition still happens on the server.  The
// microphone stream is cut into short, self-contained segments (each segment is its own complete
// audio file), uploaded one at a time through the normal consent-gated transcription job API, and
// the returned text is appended in order.  Segment edges can split a word, so the final text must
// always be reviewed by the nurse before submission.
import { useCallback, useEffect, useRef, useState } from 'react';
import { uploadAndTranscribeAudio } from '../services/api';

export interface LiveSegment {
  id: number;
  status: 'recording' | 'transcribing' | 'done' | 'error';
  text: string;
  error?: string;
  language?: string;
}

interface Options {
  language: string;
  consent: boolean;
  segmentSeconds?: number;
}

const MIME_PREFERENCE = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
const MIN_SEGMENT_BYTES = 2500; // smaller than this is silence / a cut-off fragment

export function useLiveTranscription({ language, consent, segmentSeconds = 15 }: Options) {
  const [segments, setSegments] = useState<LiveSegment[]>([]);
  const [active, setActive] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRef = useRef(false);
  const pausedRef = useRef(false);
  const nextId = useRef(1);
  const queue = useRef<Array<{ id: number; blob: Blob }>>([]);
  const draining = useRef(false);
  const idleResolvers = useRef<Array<() => void>>([]);
  const languageRef = useRef(language);
  const consentRef = useRef(consent);
  const startSegmentRef = useRef<() => void>(() => {});
  useEffect(() => {
    languageRef.current = language;
    consentRef.current = consent;
  }, [language, consent]);

  const patch = (id: number, change: Partial<LiveSegment>) =>
    setSegments((prev) => prev.map((s) => (s.id === id ? { ...s, ...change } : s)));

  const notifyIdle = () => {
    if (!draining.current && queue.current.length === 0 && !recorderRef.current) {
      idleResolvers.current.splice(0).forEach((resolve) => resolve());
    }
  };

  const drain = useCallback(async () => {
    if (draining.current) return;
    draining.current = true;
    while (queue.current.length > 0) {
      const item = queue.current.shift()!;
      patch(item.id, { status: 'transcribing' });
      try {
        const result = await uploadAndTranscribeAudio(item.blob, languageRef.current, `live_${item.id}.webm`, {
          recordingConsent: consentRef.current,
        });
        patch(item.id, { status: 'done', text: (result.transcript || '').trim(), language: result.language });
      } catch (err) {
        patch(item.id, { status: 'error', error: (err as Error).message });
      }
    }
    draining.current = false;
    notifyIdle();
  }, []);

  const startSegment = useCallback(() => {
    const stream = streamRef.current;
    if (!stream || !activeRef.current || pausedRef.current) return;
    const mime = MIME_PREFERENCE.find((m) => MediaRecorder.isTypeSupported(m));
    const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks: Blob[] = [];
    const id = nextId.current++;
    recorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };
    recorder.onstop = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      recorderRef.current = null;
      const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
      if (blob.size >= MIN_SEGMENT_BYTES) {
        setSegments((prev) => [...prev, { id, status: 'transcribing', text: '' }]);
        queue.current.push({ id, blob });
        void drain();
      }
      if (activeRef.current && !pausedRef.current) startSegmentRef.current();
      else notifyIdle();
    };

    recorder.start();
    timerRef.current = setTimeout(() => {
      if (recorder.state === 'recording') recorder.stop();
    }, segmentSeconds * 1000);
  }, [drain, segmentSeconds]);
  useEffect(() => {
    startSegmentRef.current = startSegment;
  }, [startSegment]);

  const start = useCallback((stream: MediaStream) => {
    if (!consentRef.current) return;
    streamRef.current = stream;
    activeRef.current = true;
    pausedRef.current = false;
    setSegments([]);
    nextId.current = 1;
    setActive(true);
    startSegment();
  }, [startSegment]);

  const pause = useCallback(() => {
    pausedRef.current = true;
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
  }, []);

  const resume = useCallback(() => {
    if (!activeRef.current) return;
    pausedRef.current = false;
    if (!recorderRef.current) startSegment();
  }, [startSegment]);

  /** Stop segmenting and resolve once every pending segment has been transcribed. */
  const stop = useCallback((): Promise<void> => {
    activeRef.current = false;
    setActive(false);
    if (timerRef.current) clearTimeout(timerRef.current);
    const done = new Promise<void>((resolve) => idleResolvers.current.push(resolve));
    if (recorderRef.current && recorderRef.current.state !== 'inactive') recorderRef.current.stop();
    else notifyIdle();
    return done;
  }, []);

  const reset = useCallback(() => {
    activeRef.current = false;
    setActive(false);
    queue.current = [];
    if (timerRef.current) clearTimeout(timerRef.current);
    setSegments([]);
  }, []);

  useEffect(() => () => {
    activeRef.current = false;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (recorderRef.current && recorderRef.current.state !== 'inactive') recorderRef.current.stop();
  }, []);

  const text = segments.filter((s) => s.status === 'done' && s.text).map((s) => s.text).join(' ');
  const pending = segments.some((s) => s.status === 'transcribing');
  const failed = segments.filter((s) => s.status === 'error').length;

  return { segments, text, active, pending, failed, start, pause, resume, stop, reset };
}
