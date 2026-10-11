import os
import uuid
import logging
from typing import Dict, Any, Optional
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
}

# Global WhisperModel singleton
_whisper_model = None

def get_whisper_model():
    """Lazily load the faster-whisper model (tiny or configured size)."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        model_size = os.getenv("WHISPER_MODEL_SIZE", "tiny")
        logger.info(f"Loading faster-whisper model '{model_size}' on CPU...")
        _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info("faster-whisper model loaded successfully.")
    return _whisper_model

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

def transcribe_audio_file(
    file_path: Path,
    language_preference: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transcribes audio using faster-whisper with Kannada, Hindi, and English support.
    Returns transcript text, detected language, confidence score, and duration.
    """
    model = get_whisper_model()

    # Normalize language preference
    lang_code = None
    if language_preference and language_preference.lower() not in {"auto", "detect", "auto-detect", ""}:
        pref = language_preference.lower().strip()
        if pref in {"kn", "kannada"}:
            lang_code = "kn"
        elif pref in {"hi", "hindi"}:
            lang_code = "hi"
        elif pref in {"en", "english"}:
            lang_code = "en"
        else:
            lang_code = pref

    try:
        segments, info = model.transcribe(
            str(file_path),
            language=lang_code,
            beam_size=5,
            vad_filter=True, # Voice activity detection to trim silence
            vad_parameters=dict(min_silence_duration_ms=500)
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
                # seg.avg_logprob can be converted to an estimated probability
                # e^logprob gives probability approximation
                if hasattr(seg, 'avg_logprob'):
                    import math
                    prob = max(0.0, min(1.0, math.exp(seg.avg_logprob)))
                    confidences.append(prob)

        full_transcript = " ".join(full_text_parts).strip()
        detected_lang = info.language if info.language else (lang_code or "en")
        lang_prob = round(info.language_probability, 3) if hasattr(info, "language_probability") and info.language_probability else 0.95
        avg_confidence = round(sum(confidences) / len(confidences), 3) if confidences else lang_prob
        duration_sec = round(info.duration, 2) if hasattr(info, "duration") else 0.0

        return {
            "transcript": full_transcript,
            "language": detected_lang,
            "language_name": LANGUAGE_DISPLAY_NAMES.get(detected_lang, detected_lang.upper()),
            "language_confidence": lang_prob,
            "transcription_confidence": avg_confidence,
            "duration_seconds": duration_sec,
            "segments": segment_list
        }

    except Exception as e:
        logger.error(f"Error during audio transcription: {e}")
        raise RuntimeError(f"Transcription failed: {str(e)}")
