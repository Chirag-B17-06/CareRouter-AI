import os
import sys
import uuid
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger("carerouter.audio")

# Directory for storing audio files locally (excluded by .gitignore)
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

ALLOWED_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac"}
ALLOWED_MIME_TYPES = {
    "audio/webm", "video/webm", "audio/wav", "audio/x-wav",
    "audio/mpeg", "audio/mp3", "audio/ogg", "audio/m4a",
    "audio/x-m4a", "audio/flac", "audio/aac", "application/octet-stream"
}

LANGUAGE_DISPLAY_NAMES = {
    "kn": "Kannada — ಕನ್ನಡ",
    "hi": "Hindi — हिन्दी",
    "en": "English",
    "uncertain": "Language uncertain"
}

# Domain clinical initial prompts conditioned in native scripts to guide Whisper's decoder
LANGUAGE_PROMPTS = {
    "kn": "ಕನ್ನಡ ವೈದ್ಯಕೀಯ ಸಂಭಾಷಣೆ: ರೋಗಿಗೆ ಎದೆ ನೋವು, ಎದೆಯಲ್ಲಿ ನೋವು, ಉಸಿರಾಟದ ತೊಂದರೆ, ಆಸ್ಪತ್ರೆ, ವೈದ್ಯರು, ಚಿಕಿತ್ಸೆ, ಮಾತ್ರೆ, ಔಷಧ, ಕೊಠಡಿ, ನನಗೆ ಎದೆ ನೋವು ಇದೆ.",
    "hi": "हिन्दी चिकित्सा परामर्श: मरीज, डॉक्टर, अस्पताल, सीने में दर्द, सांस लेने में तकलीफ, बुखार, दवा, कमरा, मेरा नाम, दर्द हो रहा है.",
    "en": "Clinical hospital emergency triage call: patient, room, chest pain, shortness of breath, vitals, IV medication, swelling.",
}

# Add NVIDIA cuBLAS / cuDNN DLL directories to DLL search path on Windows
def _setup_nvidia_dll_paths():
    """Ensure Windows can locate cublas64_12.dll and cudnn64_9.dll installed via pip wheels."""
    if sys.platform == "win32":
        prefix_path = Path(sys.prefix)
        for bin_dir in prefix_path.glob("Lib/site-packages/nvidia/*/bin"):
            if bin_dir.is_dir():
                try:
                    os.add_dll_directory(str(bin_dir.resolve()))
                except Exception:
                    pass
                os.environ["PATH"] = str(bin_dir.resolve()) + ";" + os.environ.get("PATH", "")

_setup_nvidia_dll_paths()

def devanagari_to_kannada(text: str) -> str:
    """
    Converts Devanagari Unicode characters (0x0900-0x097F) to Kannada Unicode characters (0x0C80-0x0CFF).
    Uses the 1:1 ISCII/Unicode block alignment (offset 0x0380).
    Ensures Kannada speech transcribed by Whisper's Indic tokenizer is displayed in native Kannada script.
    """
    res = []
    for ch in text:
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F:
            kn_cp = cp + 0x0380
            res.append(chr(kn_cp) if (0x0C80 <= kn_cp <= 0x0CFF) else ch)
        else:
            res.append(ch)
    return "".join(res)

def normalize_kannada_clinical_orthography(text: str) -> str:
    """
    Normalizes common acoustic/phonetic variations in Kannada STT transcripts:
    E.g., spoken 'ಎದೆ ನೋವು' (ede novu = chest pain) is sometimes transcribed phonetically
    as 'ಯದೆ ನೋವು' or 'ಯಾದೆ ನೋವು' due to the initial palatal glide.
    """
    if not text:
        return text
    normalized = text
    # Standardize phonetic glide variations for chest pain in Kannada
    normalized = re.sub(r'\b(?:ಯದೆ|ಯಾದೆ)\s+ನೋವು\b', 'ಎದೆ ನೋವು', normalized)
    normalized = re.sub(r'\b(?:ಯದೆ|ಯಾದೆ)\s+ನೋವ\b', 'ಎದೆ ನೋವು', normalized)
    normalized = re.sub(r'\b(?:ಯದೆ|ಯಾದೆ)ನೋವು\b', 'ಎದೆನೋವು', normalized)
    return normalized

# Global WhisperModel singleton
_whisper_model = None
_model_device = "cpu"
_model_compute_type = "int8"

def get_whisper_model():
    """
    Lazily loads the faster-whisper model singleton.
    Uses 'medium' model by default for high Kannada, Hindi, and English accuracy.
    Automatically leverages NVIDIA GPU with CUDA (float16) when available,
    with robust fallback to CPU (int8) with multi-threading.
    """
    global _whisper_model, _model_device, _model_compute_type
    if _whisper_model is None:
        import ctranslate2
        from faster_whisper import WhisperModel

        model_size = os.getenv("WHISPER_MODEL_SIZE", "medium")
        cuda_available = False
        try:
            cuda_count = ctranslate2.get_cuda_device_count()
            cuda_available = (cuda_count > 0)
        except Exception as e:
            logger.warning(f"CUDA check error: {e}")

        if cuda_available:
            try:
                logger.info(f"Attempting to load faster-whisper '{model_size}' on GPU (CUDA float16)...")
                _whisper_model = WhisperModel(model_size, device="cuda", compute_type="float16")
                _model_device = "cuda"
                _model_compute_type = "float16"
                logger.info(f"faster-whisper '{model_size}' successfully loaded on GPU (CUDA float16).")
                return _whisper_model
            except Exception as cuda_err:
                logger.warning(f"Failed to load model on CUDA ({cuda_err}). Falling back to CPU...")

        # Fallback to CPU with multi-threading
        cpu_threads = min(os.cpu_count() or 4, 8)
        logger.info(f"Loading faster-whisper '{model_size}' on CPU (int8, threads={cpu_threads})...")
        _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=cpu_threads)
        _model_device = "cpu"
        _model_compute_type = "int8"
        logger.info(f"faster-whisper '{model_size}' loaded successfully on CPU.")

    return _whisper_model

def get_engine_status() -> Dict[str, Any]:
    """Returns the current model, device, and acceleration status."""
    return {
        "engine": "faster-whisper",
        "model_size": os.getenv("WHISPER_MODEL_SIZE", "medium"),
        "device": _model_device,
        "compute_type": _model_compute_type,
        "is_loaded": (_whisper_model is not None)
    }

def validate_audio_file(filename: str, file_size: int, content_type: Optional[str] = None):
    """
    Validate audio file size, extension, and content type.
    Raises ValueError with a clear explanation if invalid.
    """
    if file_size <= 0:
        raise ValueError("The provided audio file is empty (0 bytes). Please record or upload a valid audio file.")

    if file_size > MAX_AUDIO_SIZE_BYTES:
        max_mb = MAX_AUDIO_SIZE_BYTES // (1024 * 1024)
        raise ValueError(f"Audio file size exceeds the maximum limit of {max_mb} MB.")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported audio format '{ext}'. Supported formats: {allowed_list}")

def detect_script(text: str) -> str:
    """Detect whether script is predominantly Kannada, Devanagari (Hindi), or Latin (English)."""
    kannada_chars = len(re.findall(r'[\u0C80-\u0CFF]', text))
    devanagari_chars = len(re.findall(r'[\u0900-\u097F]', text))
    latin_chars = len(re.findall(r'[a-zA-Z]', text))

    if kannada_chars > 2 and kannada_chars >= devanagari_chars:
        return "kn"
    elif devanagari_chars > 2 and devanagari_chars >= kannada_chars:
        return "hi"
    elif latin_chars > 2:
        return "en"
    return "unknown"

def transcribe_audio_file(
    file_path: Path,
    language_preference: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transcribes audio using faster-whisper with state-of-the-art Kannada, Hindi, and English support.
    Supports automatic language detection and manual language selection ('kn', 'hi', 'en').
    Preserves native scripts (ಕನ್ನಡ for Kannada, हिन्दी for Hindi, English for English).
    Includes silence detection and robust VAD fallback.
    Returns transcript text, detected language, confidence score, duration, and silence status.
    """
    model = get_whisper_model()

    # Normalize language preference
    lang_code = None
    if language_preference and language_preference.lower() not in {"auto", "detect", "auto-detect", "", "uncertain"}:
        pref = language_preference.lower().strip()
        if pref in {"kn", "kannada"}:
            lang_code = "kn"
        elif pref in {"hi", "hindi"}:
            lang_code = "hi"
        elif pref in {"en", "english"}:
            lang_code = "en"
        else:
            lang_code = pref

    # Step A: Check audio amplitude using PyAV to detect complete silence
    max_amplitude = 0.0
    try:
        import av, numpy as np
        with av.open(str(file_path), mode="r", metadata_errors="ignore") as container:
            if container.streams.audio:
                for frame in container.decode(audio=0):
                    arr = frame.to_ndarray()
                    if np.issubdtype(arr.dtype, np.integer):
                        frame_max = float(np.max(np.abs(arr))) / 32768.0
                    else:
                        frame_max = float(np.max(np.abs(arr)))
                    if frame_max > max_amplitude:
                        max_amplitude = frame_max
    except Exception as e:
        logger.warning(f"Could not inspect audio amplitude: {e}")

    is_silent = (max_amplitude < 0.001)
    if is_silent:
        logger.info(f"Audio file '{file_path.name}' appears completely silent (max amplitude: {max_amplitude:.5f}).")

    try:
        # Step B: Select initial prompt based on language
        initial_prompt = LANGUAGE_PROMPTS.get(lang_code) if lang_code else None

        # Transcribe with faster-whisper:
        # - beam_size=5 for maximum accuracy
        # - condition_on_previous_text=False prevents repetitive loop hallucinations
        # - vad_filter with safe padding prevents clipping quiet word endings
        # - task='transcribe' guarantees native transcription without English translation
        segments, info = model.transcribe(
            str(file_path),
            language=lang_code,
            initial_prompt=initial_prompt,
            beam_size=5,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=400),
            task="transcribe"
        )

        segment_list = []
        full_text_parts = []
        confidences = []

        for seg in segments:
            text_part = seg.text.strip()
            if text_part:
                full_text_parts.append(text_part)
                segment_list.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": text_part
                })
                if hasattr(seg, 'avg_logprob'):
                    import math
                    prob = max(0.0, min(1.0, math.exp(seg.avg_logprob)))
                    confidences.append(prob)

        full_transcript = " ".join(full_text_parts).strip()

        # Step C: Fallback pass if first pass returned empty on non-silent audio
        if not full_transcript and not is_silent and hasattr(info, "duration") and info.duration > 0.5:
            logger.info("First pass with VAD returned empty; running fallback without VAD...")
            segments_fallback, info = model.transcribe(
                str(file_path),
                language=lang_code,
                initial_prompt=initial_prompt,
                beam_size=5,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False,
                task="transcribe"
            )
            for seg in segments_fallback:
                text_part = seg.text.strip()
                if text_part:
                    full_text_parts.append(text_part)
                    segment_list.append({
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": text_part
                    })
                    if hasattr(seg, 'avg_logprob'):
                        import math
                        prob = max(0.0, min(1.0, math.exp(seg.avg_logprob)))
                        confidences.append(prob)
            full_transcript = " ".join(full_text_parts).strip()

        # Step D: Script Detection and Language Resolution
        detected_script = detect_script(full_transcript)
        whisper_lang = getattr(info, "language", None) or "en"
        raw_prob = float(getattr(info, "language_probability", 0.0) or 0.0)

        # Urdu is phonetically identical to spoken Hindi; map to Hindi
        if whisper_lang == "ur":
            whisper_lang = "hi"

        is_uncertain = False
        suggested_lang = None

        if lang_code:
            # User explicitly selected language
            final_lang = lang_code
            lang_confidence = 1.0
        else:
            # Auto-detect mode:
            # 1. Ground truth from transcript script:
            if detected_script == "kn":
                final_lang = "kn"
                lang_confidence = max(raw_prob, 0.90)
            elif detected_script == "hi":
                final_lang = "hi"
                lang_confidence = max(raw_prob, 0.90)
            elif detected_script == "en" and whisper_lang in {"en", "hi", "kn"}:
                final_lang = whisper_lang if whisper_lang != "en" and raw_prob >= 0.50 else "en"
                lang_confidence = raw_prob if raw_prob >= 0.50 else 0.85
            # 2. Whisper acoustic detection:
            elif whisper_lang in {"kn", "hi", "en"} and raw_prob >= 0.35:
                final_lang = whisper_lang
                lang_confidence = round(raw_prob, 3)
            # 3. Check target probabilities if info.all_language_probs exists:
            else:
                target_probs = {}
                if hasattr(info, "all_language_probs") and info.all_language_probs:
                    for l_code, p in info.all_language_probs:
                        norm_l = "hi" if l_code == "ur" else l_code
                        if norm_l in {"kn", "hi", "en"}:
                            target_probs[norm_l] = target_probs.get(norm_l, 0.0) + float(p)

                if target_probs and max(target_probs.values()) >= 0.30:
                    best_l = max(target_probs, key=target_probs.get)
                    final_lang = best_l
                    lang_confidence = round(target_probs[best_l], 3)
                else:
                    # Genuinely ambiguous or foreign audio
                    is_uncertain = True
                    final_lang = "uncertain"
                    lang_confidence = round(raw_prob, 3)
                    suggested_lang = whisper_lang if whisper_lang in {"kn", "hi", "en"} else "en"

        # Step E: Native Script & Orthography Normalization
        if final_lang == "kn" or lang_code == "kn":
            # If Devanagari characters were output, convert to Kannada Unicode
            if any('\u0900' <= ch <= '\u097F' for ch in full_transcript):
                full_transcript = devanagari_to_kannada(full_transcript)
                for seg in segment_list:
                    seg["text"] = devanagari_to_kannada(seg["text"])

            # Normalize Kannada phonetic orthography (e.g., ಯದೆ ನೋವು -> ಎದೆ ನೋವು)
            full_transcript = normalize_kannada_clinical_orthography(full_transcript)
            for seg in segment_list:
                seg["text"] = normalize_kannada_clinical_orthography(seg["text"])

        avg_confidence = round(sum(confidences) / len(confidences), 3) if confidences else (
            lang_confidence if not is_uncertain else 0.40
        )
        duration_sec = round(info.duration, 2) if hasattr(info, "duration") else 0.0
        lang_name = "Language uncertain" if is_uncertain else LANGUAGE_DISPLAY_NAMES.get(final_lang, final_lang.upper())

        return {
            "transcript": full_transcript,
            "language": final_lang,
            "language_name": lang_name,
            "language_confidence": lang_confidence,
            "transcription_confidence": avg_confidence,
            "duration_seconds": duration_sec,
            "segments": segment_list,
            "is_silent": is_silent,
            "max_amplitude": round(max_amplitude, 4),
            "language_uncertain": is_uncertain,
            "suggested_language": suggested_lang
        }

    except Exception as e:
        logger.error(f"Error during audio transcription: {e}")
        raise RuntimeError(f"Transcription failed: {str(e)}")
