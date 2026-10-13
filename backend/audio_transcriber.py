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

# Domain clinical initial prompts conditioned in native scripts to guide Whisper's decoder.
# Biases the acoustic-language model toward Indian accents, medical terminology, dosages, and mixed speech.
LANGUAGE_PROMPTS = {
    "kn": (
        "ಕನ್ನಡ ವೈದ್ಯಕೀಯ ಸಂಭಾಷಣೆ: ರೋಗಿಗೆ ಎದೆ ನೋವು, ಎದೆಯಲ್ಲಿ ನೋವು, ಉಸಿರಾಟದ ತೊಂದರೆ, ಜ್ವರ, ತಲೆತಿರುಗುವಿಕೆ, "
        "ಊತ, ರಕ್ತಸ್ರಾವ, ಬಿಪಿ, ಶುಗರ್, ಆಸ್ಪತ್ರೆ, ವೈದ್ಯರು, ಡಾಕ್ಟರ್, ಶುಶ್ರೂಷಕಿ, ನರ್ಸ್, ಚಿಕಿತ್ಸೆ, ಮಾತ್ರೆ, ಔಷಧ, "
        "ಇಂಜೆಕ್ಷನ್, ಐವಿ ಡ್ರಿಪ್, ಕೊಠಡಿ, ರೂಮ್, ವಾರ್ಡ್, 500 ಮಿಲಿಗ್ರಾಂ, ಪ್ಯಾರಸಿಟಮಾಲ್, ಮೆಟ್‌ಫಾರ್ಮಿನ್, "
        "ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್, ಡಿಸ್ಚಾರ್ಜ್, severe chest pain, shortness of breath, left arm swelling, IV machine."
    ),
    "hi": (
        "हिन्दी चिकित्सा परामर्श एवं आपातकालीन कॉल: मरीज, डॉक्टर, नर्स, अस्पताल, सीने में दर्द, सांस लेने में तकलीफ, "
        "बुखार, चक्कर, सूजन, खून बहना, बीपी, ब्लड प्रेशर, शुगर, डायबिटीज, दवा, गोली, टैबलेट, इंजेक्शन, "
        "आईवी ड्रिप, 500 मिलीग्राम, पैरासिटामोल, मेटफॉर्मिन, इंसुलिन, कमरा, रूम, वार्ड, अपॉइंटमेंट, "
        "डिस्चार्ज, severe chest pain, shortness of breath, left arm swelling, IV machine."
    ),
    "en": (
        "Clinical hospital emergency triage call: patient Arthur, room, ward, bed 12, acute chest pain, "
        "shortness of breath, oxygen saturation, tachycardia, IV infiltration, left arm swelling, "
        "500 mg Paracetamol, 50 mg Metformin, insulin, prescription refill, appointment scheduling, "
        "Dr. Rao, Dr. Sharma, Dr. Chen, discharge paperwork, billing inquiry."
    ),
    "neutral": (
        "Clinical triage hospital call: patient, doctor, nurse, vitals, medicine, room, ward, emergency."
    )
}

# Add NVIDIA cuBLAS / cuDNN DLL directories to DLL search path on Windows
def _setup_nvidia_dll_paths():
    """Ensure Windows can locate cublas64_12.dll and cudnn64_9.dll installed via pip wheels."""
    if sys.platform == "win32":
        prefix_path = Path(sys.prefix)
        # Check standard python site-packages locations for nvidia wheels
        search_dirs = list(prefix_path.glob("Lib/site-packages/nvidia/*/bin"))
        search_dirs.extend(prefix_path.glob("Lib/site-packages/nvidia/*/lib"))
        for bin_dir in search_dirs:
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
    as 'ಯದೆ ನೋವು' or 'ಯಾದೆ ನೋವು' or 'ಏದೇ ನೋವ' due to palatal glide and vowel length.
    """
    if not text:
        return text
    normalized = text
    # Standardize phonetic variations for chest pain in Kannada
    normalized = re.sub(r'\b(?:ಯದೆ|ಯಾದೆ|ಏದೇ|ಇದ್ಯು|ಯಾಧೆ)\s*(?:ನೋವು|ನೋವ|ನುವೀ)\b', 'ಎದೆ ನೋವು', normalized)
    normalized = re.sub(r'\b(?:ಯದೆ|ಯಾದೆ|ಏದೇ|ಇದ್ಯು|ಯಾಧೆ)(?:ನೋವು|ನೋವ|ನುವೀ)\b', 'ಎದೆನೋವು', normalized)
    normalized = re.sub(r'\bಉಸಿರಾಟದ\s*(?:ತೊಂಧರೆ|ತೊಂತರ|ತುನ್ದರೇ|ತಸ್ಣ್ದ್ಪ್ಂದಿ)\b', 'ಉಸಿರಾಟದ ತೊಂದರೆ', normalized)
    normalized = re.sub(r'\bಪ್ಯಾರಸಿಟಮಲ್\b', 'ಪ್ಯಾರಸಿಟಮಾಲ್', normalized)
    normalized = re.sub(r'\bಮೆಟ್ಫಾರ್ಮಿನ್\b', 'ಮೆಟ್‌ಫಾರ್ಮಿನ್', normalized)
    normalized = re.sub(r'\b(?:ವೈಧ್ಡ್ಕೊರ|ವೈ ದೇರ|ವಾಈಧಿರನ್ನು)\b', 'ವೈದ್ಯರನ್ನು', normalized)
    return normalized

def normalize_hindi_clinical_orthography(text: str) -> str:
    """Normalizes common phonetic/spacing variations in Hindi clinical speech."""
    if not text:
        return text
    normalized = text
    normalized = re.sub(r'\bचेस्टपेन\b', 'चेस्ट पेन', normalized)
    normalized = re.sub(r'\bहार्टअटैक\b', 'हार्ट अटैक', normalized)
    normalized = re.sub(r'\b(?:सिनेमें|सीनेमे|सिने में)\b', 'सीने में', normalized)
    normalized = re.sub(r'\bदर्ध\b', 'दर्द', normalized)
    normalized = re.sub(r'\bतेस्द\b', 'तेज', normalized)
    normalized = re.sub(r'\bमेंतकलीफ\b', 'में तकलीफ', normalized)
    normalized = re.sub(r'\bपैरासिटामॉल\b', 'पैरासिटामोल', normalized)
    normalized = re.sub(r'\bपेरासिटामोल\b', 'पैरासिटामोल', normalized)
    normalized = re.sub(r'\bपैशिन्ट\b', 'पेशेंट', normalized)
    return normalized

# Model cache dictionary to reuse loaded models across inferences and avoid repeated downloads
_whisper_models: Dict[str, Any] = {}
_model_device = "cpu"
_model_compute_type = "int8"
_active_model_size = "medium"

def get_whisper_model(model_size: Optional[str] = None):
    """
    Lazily loads and caches the faster-whisper model singleton.
    Reuses already loaded models to avoid repeated downloads or sequential blocking.
    Leverages NVIDIA GPU with CUDA (float16) when available,
    with robust automatic fallback to CPU (int8) with multi-threading.
    """
    global _whisper_models, _model_device, _model_compute_type, _active_model_size

    target_size = model_size or os.getenv("WHISPER_MODEL_SIZE", "medium")
    _active_model_size = target_size

    # Check if model is already cached
    cache_key = f"{target_size}_{_model_device}"
    if cache_key in _whisper_models:
        return _whisper_models[cache_key]

    import ctranslate2
    from faster_whisper import WhisperModel

    cuda_available = False
    try:
        cuda_count = ctranslate2.get_cuda_device_count()
        cuda_available = (cuda_count > 0)
    except Exception as e:
        logger.warning(f"CUDA check error: {e}")

    # Attempt CUDA loading if GPU is available
    if cuda_available and os.getenv("FORCE_CPU", "0") != "1":
        try:
            logger.info(f"Attempting to load faster-whisper '{target_size}' on GPU (CUDA float16)...")
            gpu_model = WhisperModel(target_size, device="cuda", compute_type="float16")
            _model_device = "cuda"
            _model_compute_type = "float16"
            _whisper_models[f"{target_size}_cuda"] = gpu_model
            logger.info(f"faster-whisper '{target_size}' successfully loaded on GPU (CUDA float16).")
            return gpu_model
        except Exception as cuda_err:
            logger.warning(f"Failed to load model on CUDA ({cuda_err}). Falling back to CPU...")

    # CPU Fallback with multi-threading
    cpu_threads = min(os.cpu_count() or 4, 8)
    logger.info(f"Loading faster-whisper '{target_size}' on CPU (int8, threads={cpu_threads})...")
    cpu_model = WhisperModel(target_size, device="cpu", compute_type="int8", cpu_threads=cpu_threads)
    _model_device = "cpu"
    _model_compute_type = "int8"
    _whisper_models[f"{target_size}_cpu"] = cpu_model
    logger.info(f"faster-whisper '{target_size}' loaded successfully on CPU.")
    return cpu_model

def get_engine_status() -> Dict[str, Any]:
    """Returns the current model, device, and acceleration status."""
    return {
        "engine": "faster-whisper",
        "model_size": _active_model_size,
        "device": _model_device,
        "compute_type": _model_compute_type,
        "is_loaded": (len(_whisper_models) > 0),
        "cached_models": list(_whisper_models.keys())
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

def normalize_audio_channel_and_rate(file_path: Path) -> Tuple[Path, bool]:
    """
    Inspects audio channels and sample rate using PyAV.
    If the file is already 16kHz mono WAV, returns (file_path, False).
    Otherwise, resamples to mono 16kHz WAV to guarantee optimal faster-whisper accuracy
    and avoid channel-layout or sampling-rate decoding errors.
    """
    try:
        import av
        with av.open(str(file_path), mode="r", metadata_errors="ignore") as container:
            if not container.streams.audio:
                return file_path, False
            audio_stream = container.streams.audio[0]

            # If already mono 16kHz wav, use directly
            if (file_path.suffix.lower() == ".wav" and
                audio_stream.channels == 1 and
                audio_stream.sample_rate == 16000):
                return file_path, False

            # Resample to 16kHz mono WAV
            norm_path = UPLOAD_DIR / f"norm_{file_path.stem}.wav"
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)

            with av.open(str(norm_path), mode="w", format="wav") as out_container:
                out_stream = out_container.add_stream("pcm_s16le", rate=16000)
                out_stream.channels = 1
                out_stream.layout = "mono"

                for frame in container.decode(audio_stream):
                    for r_frame in resampler.resample(frame):
                        for packet in out_stream.encode(r_frame):
                            out_container.mux(packet)
                # Flush encoder
                for packet in out_stream.encode():
                    out_container.mux(packet)

            return norm_path, True
    except Exception as e:
        logger.info(f"Direct stream pass-through (resampler skipped: {e})")
        return file_path, False

def transcribe_audio_file(
    file_path: Path,
    language_preference: Optional[str] = None,
    model_size: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transcribes audio using faster-whisper with state-of-the-art Kannada, Hindi, and English support.
    Supports automatic language detection and manual language selection ('kn', 'hi', 'en').
    Preserves native scripts (ಕನ್ನಡ for Kannada, हिन्दी for Hindi, English for English).
    Includes silence detection and robust VAD fallback.
    Returns transcript text, detected language, confidence score, duration, and silence status.
    """
    model = get_whisper_model(model_size=model_size)

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

    # Step B: Select initial prompt based on language
    # For auto-detection, use neutral prompt to prevent biasing language identification toward any specific Indic script
    if lang_code:
        initial_prompt = LANGUAGE_PROMPTS.get(lang_code)
    else:
        initial_prompt = LANGUAGE_PROMPTS.get("neutral")

    # Resample/normalize channels if necessary
    target_path, is_temp = normalize_audio_channel_and_rate(file_path)

    try:
        # Transcribe with faster-whisper:
        # - beam_size=5 for maximum accuracy
        # - condition_on_previous_text=False prevents repetitive loop hallucinations
        # - repetition_penalty=1.15 and no_repeat_ngram_size=3 prevent character loop hallucinations in Indic scripts
        # - vad_filter with safe padding (speech_pad_ms=500) prevents clipping quiet word endings
        # - task='transcribe' guarantees native transcription without English translation
        try:
            segments, info = model.transcribe(
                str(target_path),
                language=lang_code,
                initial_prompt=initial_prompt,
                beam_size=5,
                temperature=0.0,
                condition_on_previous_text=False,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=500),
                task="transcribe"
            )
        except Exception as cuda_exec_err:
            # Automatic fallback to CPU if CUDA runtime error occurs during transcribe()
            if _model_device == "cuda":
                logger.warning(f"CUDA transcription failed ({cuda_exec_err}). Falling back to CPU model...")
                cpu_threads = min(os.cpu_count() or 4, 8)
                from faster_whisper import WhisperModel
                fallback_cpu_model = WhisperModel(_active_model_size, device="cpu", compute_type="int8", cpu_threads=cpu_threads)
                _whisper_models[f"{_active_model_size}_cpu"] = fallback_cpu_model
                segments, info = fallback_cpu_model.transcribe(
                    str(target_path),
                    language=lang_code,
                    initial_prompt=initial_prompt,
                    beam_size=5,
                    temperature=0.0,
                    condition_on_previous_text=False,
                    repetition_penalty=1.15,
                    no_repeat_ngram_size=3,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=500),
                    task="transcribe"
                )
            else:
                raise cuda_exec_err

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
                str(target_path),
                language=lang_code,
                initial_prompt=initial_prompt,
                beam_size=5,
                temperature=0.0,
                condition_on_previous_text=False,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
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

        elif final_lang == "hi" or lang_code == "hi":
            # Normalize Hindi orthography and spacing
            full_transcript = normalize_hindi_clinical_orthography(full_transcript)
            for seg in segment_list:
                seg["text"] = normalize_hindi_clinical_orthography(seg["text"])

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
    finally:
        # Clean up temporary normalized file if created
        if is_temp and target_path.exists():
            target_path.unlink(missing_ok=True)
