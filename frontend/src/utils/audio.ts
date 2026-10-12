// Web Audio API medical telemetry synthesizer (no external audio assets needed)
class SoundManager {
  private ctx: AudioContext | null = null;
  public enabled: boolean = true;

  private getContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
    return this.ctx;
  }

  public playEmergencyAlert() {
    if (!this.enabled) return;
    try {
      const ctx = this.getContext();
      if (!ctx) return;

      const now = ctx.currentTime;
      // High-priority medical chime: 880Hz -> 1046Hz -> 880Hz
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, now); // A5
      osc.frequency.setValueAtTime(1046.5, now + 0.15); // C6
      osc.frequency.setValueAtTime(880, now + 0.3);

      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.55);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.6);
    } catch (e) {
      console.warn("Audio playback not allowed yet", e);
    }
  }

  public playSuccessChime() {
    if (!this.enabled) return;
    try {
      const ctx = this.getContext();
      if (!ctx) return;

      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.setValueAtTime(659.25, now + 0.1); // E5
      osc.frequency.setValueAtTime(783.99, now + 0.2); // G5

      gain.gain.setValueAtTime(0.1, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.45);
    } catch (e) {
      console.warn("Audio playback error", e);
    }
  }
}

export const soundManager = new SoundManager();

function getAudioContextConstructor(): typeof AudioContext | null {
  if (typeof window === 'undefined') return null;
  return window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
}

/** Mix to mono and resample with linear interpolation. */
function resampleMono(buffer: AudioBuffer, targetRate: number): Float32Array {
  const srcRate = buffer.sampleRate;
  const srcLength = buffer.length;
  const channels = buffer.numberOfChannels;
  const duration = srcLength / srcRate;
  const targetLength = Math.max(1, Math.round(duration * targetRate));
  const out = new Float32Array(targetLength);
  const channelData: Float32Array[] = [];
  for (let c = 0; c < channels; c++) {
    channelData.push(buffer.getChannelData(c));
  }

  if (srcRate === targetRate) {
    for (let i = 0; i < srcLength; i++) {
      let sum = 0;
      for (let c = 0; c < channels; c++) sum += channelData[c][i];
      out[i] = sum / channels;
    }
    return out;
  }

  for (let i = 0; i < targetLength; i++) {
    const srcIndex = (i * srcRate) / targetRate;
    const i0 = Math.min(srcLength - 1, Math.floor(srcIndex));
    const i1 = Math.min(srcLength - 1, i0 + 1);
    const frac = srcIndex - i0;
    let s0 = 0;
    let s1 = 0;
    for (let c = 0; c < channels; c++) {
      s0 += channelData[c][i0];
      s1 += channelData[c][i1];
    }
    s0 /= channels;
    s1 /= channels;
    out[i] = s0 * (1 - frac) + s1 * frac;
  }
  return out;
}

function floatToWavArrayBuffer(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const numChannels = 1;
  const bitsPerSample = 16;
  const blockAlign = (numChannels * bitsPerSample) / 8;
  const byteRate = sampleRate * blockAlign;
  const dataSize = samples.length * blockAlign;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitsPerSample, true);
  writeString(36, 'data');
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  return buffer;
}

/**
 * Decode a MediaRecorder/browser audio Blob with Web Audio, then re-encode 16 kHz
 * mono PCM WAV. Chrome can decode its own chunked WebM even when PyAV/Whisper cannot.
 */
export async function decodeBrowserAudioToWav(input: Blob): Promise<Blob> {
  const AudioCtx = getAudioContextConstructor();
  if (!AudioCtx) {
    throw new Error('Web Audio API is not available');
  }
  const ctx = new AudioCtx();
  try {
    if (ctx.state === 'suspended') {
      await ctx.resume();
    }
    const arrayBuffer = await input.arrayBuffer();
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
    const samples = resampleMono(audioBuffer, 16000);
    const wav = floatToWavArrayBuffer(samples, 16000);
    return new Blob([wav], { type: 'audio/wav' });
  } finally {
    if (ctx.state !== 'closed') {
      await ctx.close().catch(() => {});
    }
  }
}
