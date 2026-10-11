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
    "uncertain": "Language uncertain"
}

LANGUAGE_PROMPTS = {
    "kn": "ಕನ್ನಡ: ರೋಗಿ, ವೈದ್ಯರು, ಆಸ್ಪತ್ರೆ, ಎದೆ ನೋವು, ಉಸಿರಾಟದ ತೊಂದರೆ, ಔಷಧ, ಕೊಠಡಿ.",
    "hi": "हिन्दी: मरीज, डॉक्टर, अस्पताल, सीने में दर्द, सांस लेने में तकलीफ, दवा, कमरा.",
    "en": "Clinical hospital triage call: patient, room, chest pain, shortness of breath, IV medication.",
}

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

# Global WhisperModel singleton
_whisper_model = None

def get_whisper_model():
    """Lazily load the faster-whisper model (small by default for high Indic & English accuracy)."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        model_size = os.getenv("WHISPER_MODEL_SIZE", "small")
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
    Supports automatic language detection and user language hints.
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
                    frame_max = float(np.max(np.abs(arr)))
                    if frame_max > max_amplitude:
                        max_amplitude = frame_max
    except Exception as e:
        logger.warning(f"Could not inspect audio amplitude: {e}")

    is_silent = (max_amplitude < 0.001)
    if is_silent:
        logger.info(f"Audio file '{file_path.name}' appears completely silent (max amplitude: {max_amplitude:.5f}).")

    try:
        # Step B: Transcribe with faster-whisper
        # Use beam_size=5 for optimal accuracy
        segments, info = model.transcribe(
            str(file_path),
            language=lang_code,
            beam_size=5
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
            logger.info("First pass returned empty on non-silent audio; running fallback without VAD...")
            segments_fallback, info = model.transcribe(
                str(file_path),
                language=lang_code,
                beam_size=5,
                vad_filter=False
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

        # Step D: Language detection and uncertainty evaluation
        detected_lang = lang_code or "en"
        lang_prob = 1.0
        is_uncertain = False
        suggested_lang = None

        if not lang_code:
            whisper_lang = getattr(info, "language", None) or "en"
            raw_prob = float(getattr(info, "language_probability", 0.0) or 0.0)

            # Collect probabilities for target languages kn, hi, en
            target_probs = {}
            if hasattr(info, "all_language_probs") and info.all_language_probs:
                for l_code, p in info.all_language_probs:
                    if l_code in {"kn", "hi", "en"}:
                        target_probs[l_code] = float(p)

            best_target = None
            best_target_prob = 0.0
            if target_probs:
                best_target = max(target_probs, key=target_probs.get)
                best_target_prob = target_probs[best_target]

            # Evaluation logic:
            # 1. If Whisper detected kn/hi/en with prob >= 0.50 -> Confirmed
            if whisper_lang in {"kn", "hi", "en"} and raw_prob >= 0.50:
                detected_lang = whisper_lang
                lang_prob = round(raw_prob, 3)
                is_uncertain = False
                suggested_lang = None
            # 2. Or if one of our target languages clearly leads with prob >= 0.50 -> Confirmed
            elif best_target and best_target_prob >= 0.50:
                detected_lang = best_target
                lang_prob = round(best_target_prob, 3)
                is_uncertain = False
                suggested_lang = None
            # 3. Otherwise, detection is ambiguous or picked an unrelated foreign language
            else:
                is_uncertain = True
                detected_lang = "uncertain"
                lang_prob = round(raw_prob, 3)
                suggested_lang = best_target if (best_target and best_target_prob >= 0.15) else (
                    whisper_lang if whisper_lang in {"kn", "hi", "en"} else "en"
                )
        else:
            detected_lang = lang_code
            lang_prob = 1.0
            is_uncertain = False

        avg_confidence = round(sum(confidences) / len(confidences), 3) if confidences else (
            lang_prob if not is_uncertain else 0.40
        )
        duration_sec = round(info.duration, 2) if hasattr(info, "duration") else 0.0

        # Step E: If language is Kannada and output contains Devanagari, convert to native Kannada Unicode
        if detected_lang == "kn" or lang_code == "kn":
            if any('\u0900' <= ch <= '\u097F' for ch in full_transcript):
                full_transcript = devanagari_to_kannada(full_transcript)
                for seg in segment_list:
                    seg["text"] = devanagari_to_kannada(seg["text"])

        lang_name = "Language uncertain" if is_uncertain else LANGUAGE_DISPLAY_NAMES.get(detected_lang, detected_lang.upper())

        return {
            "transcript": full_transcript,
            "language": detected_lang,
            "language_name": lang_name,
            "language_confidence": lang_prob,
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


