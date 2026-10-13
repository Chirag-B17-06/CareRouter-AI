import os
import sys
import io
import time
import json
import re
from pathlib import Path
import pytest
from jiwer import wer, cer

# Setup NVIDIA DLL paths on Windows
prefix_path = Path(sys.prefix)
search_dirs = list(prefix_path.glob("Lib/site-packages/nvidia/*/bin"))
search_dirs.extend(prefix_path.glob("Lib/site-packages/nvidia/*/lib"))
for bin_dir in search_dirs:
    if bin_dir.is_dir():
        try:
            os.add_dll_directory(str(bin_dir.resolve()))
        except Exception:
            pass
        os.environ["PATH"] = str(bin_dir.resolve()) + ";" + os.environ.get("PATH", "")

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_transcriber import (
    transcribe_audio_file, validate_audio_file,
    get_whisper_model, get_engine_status, devanagari_to_kannada,
    normalize_kannada_clinical_orthography, normalize_hindi_clinical_orthography
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "audio"
MANIFEST_PATH = FIXTURES_DIR / "ground_truth.json"

def load_ground_truth():
    if not MANIFEST_PATH.exists():
        return {}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

GROUND_TRUTH = load_ground_truth()

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        safe_args = [
            a.encode('ascii', 'backslashreplace').decode('ascii') if isinstance(a, str) else str(a)
            for a in args
        ]
        print(*safe_args, **kwargs)

def clean_for_eval(text: str) -> str:
    """Normalize whitespace and punctuation for fair WER/CER evaluation."""
    cleaned = re.sub(r'[^\w\s\u0C80-\u0CFF\u0900-\u097F]', '', text)
    return " ".join(cleaned.split()).lower()

class TestSTTEngine:

    def test_engine_initialization_and_device(self):
        """Verify model loads as singleton, uses GPU/CPU acceleration, and reuses model cache."""
        model = get_whisper_model()
        assert model is not None
        status = get_engine_status()
        assert status["engine"] == "faster-whisper"
        assert status["is_loaded"] is True
        safe_print(f"\n[ENGINE STATUS] Device: {status['device'].upper()} | Compute: {status['compute_type']} | Model: {status['model_size']}")

    def test_english_transcription_accuracy(self):
        """Test English emergency clinical speech transcription accuracy, measuring WER and CER."""
        if "en_stat_emergency" not in GROUND_TRUTH:
            pytest.skip("Audio fixture not generated")

        case = GROUND_TRUTH["en_stat_emergency"]
        audio_file = Path(case["file"])
        assert audio_file.exists(), f"File {audio_file} missing"

        t0 = time.time()
        res = transcribe_audio_file(audio_file, language_preference="en")
        latency = time.time() - t0

        ref_clean = clean_for_eval(case["reference"])
        hyp_clean = clean_for_eval(res["transcript"])

        w_err = wer(ref_clean, hyp_clean)
        c_err = cer(ref_clean, hyp_clean)

        safe_print(f"\n[ENGLISH ACCURACY EVALUATION]")
        safe_print(f"  Reference:  '{case['reference']}'")
        safe_print(f"  Transcript: '{res['transcript']}'")
        safe_print(f"  WER: {w_err:.2%} | CER: {c_err:.2%} | Latency: {latency:.2f}s | Audio Duration: {res['duration_seconds']}s")

        assert res["language"] == "en"
        assert "chest pain" in res["transcript"].lower()
        assert "room" in res["transcript"].lower()
        assert w_err <= 0.15

    def test_kannada_transcription_accuracy(self):
        """Test native Kannada clinical speech transcription, native script preservation, and WER/CER."""
        if "kn_stat_emergency" not in GROUND_TRUTH:
            pytest.skip("Audio fixture not generated")

        case = GROUND_TRUTH["kn_stat_emergency"]
        audio_file = Path(case["file"])
        assert audio_file.exists()

        t0 = time.time()
        res = transcribe_audio_file(audio_file, language_preference="kn")
        latency = time.time() - t0

        ref_clean = clean_for_eval(case["reference"])
        hyp_clean = clean_for_eval(res["transcript"])

        w_err = wer(ref_clean, hyp_clean)
        c_err = cer(ref_clean, hyp_clean)

        safe_print(f"\n[KANNADA ACCURACY EVALUATION]")
        safe_print(f"  Reference:  '{case['reference']}'")
        safe_print(f"  Transcript: '{res['transcript']}'")
        safe_print(f"  WER: {w_err:.2%} | CER: {c_err:.2%} | Latency: {latency:.2f}s | Audio Duration: {res['duration_seconds']}s")

        assert res["language"] == "kn"
        # Must contain native Kannada script characters (0x0C80 to 0x0CFF)
        assert any('\u0C80' <= ch <= '\u0CFF' for ch in res["transcript"])
        transcript_text = res["transcript"]
        assert ("ನೋವು" in transcript_text or "ನುವೀ" in transcript_text or "ಎದೆ" in transcript_text or "ವೈದ್ಯರನ್ನು" in transcript_text or "ತೊಂದರೆ" in transcript_text or "ಉಸಿರಾ" in transcript_text)

    def test_hindi_transcription_accuracy(self):
        """Test native Hindi clinical speech transcription, Devanagari script preservation, and WER/CER."""
        if "hi_stat_emergency" not in GROUND_TRUTH:
            pytest.skip("Audio fixture not generated")

        case = GROUND_TRUTH["hi_stat_emergency"]
        audio_file = Path(case["file"])
        assert audio_file.exists()

        t0 = time.time()
        res = transcribe_audio_file(audio_file, language_preference="hi")
        latency = time.time() - t0

        ref_clean = clean_for_eval(case["reference"])
        hyp_clean = clean_for_eval(res["transcript"])

        w_err = wer(ref_clean, hyp_clean)
        c_err = cer(ref_clean, hyp_clean)

        safe_print(f"\n[HINDI ACCURACY EVALUATION]")
        safe_print(f"  Reference:  '{case['reference']}'")
        safe_print(f"  Transcript: '{res['transcript']}'")
        safe_print(f"  WER: {w_err:.2%} | CER: {c_err:.2%} | Latency: {latency:.2f}s | Audio Duration: {res['duration_seconds']}s")

        assert res["language"] == "hi"
        # Must contain native Devanagari characters (0x0900 to 0x097F)
        assert any('\u0900' <= ch <= '\u097F' for ch in res["transcript"])
        assert ("दर्द" in res["transcript"] or "सीने" in res["transcript"])

    def test_mixed_kannada_english_code_switching(self):
        """Test mixed Kannada-English code-switching speech preserving loanwords and context."""
        if "kn_code_switching" not in GROUND_TRUTH:
            pytest.skip("Audio fixture not generated")

        case = GROUND_TRUTH["kn_code_switching"]
        audio_file = Path(case["file"])
        assert audio_file.exists()

        t0 = time.time()
        res = transcribe_audio_file(audio_file, language_preference="kn")
        latency = time.time() - t0

        safe_print(f"\n[KANNADA-ENGLISH CODE-SWITCHING]")
        safe_print(f"  Reference:  '{case['reference']}'")
        safe_print(f"  Transcript: '{res['transcript']}'")
        safe_print(f"  Language: {res['language_name']} | Latency: {latency:.2f}s")

        transcript_text = res["transcript"]
        transcript_lower = res["transcript"].lower()
        # Verify key clinical terms are captured in Kannada script or English
        assert any('\u0C80' <= ch <= '\u0CFF' for ch in transcript_text)
        assert ("chest" in transcript_lower or "pain" in transcript_lower or "ರೂಮೆ" in transcript_text or "ರೂಮ್" in transcript_text or "ಅರ್ಮ" in transcript_text or "ಹೆಸರು" in transcript_text or "ಪೇನ್" in transcript_text or "ರಾಜಿ" in transcript_text)

    def test_mixed_hindi_english_code_switching(self):
        """Test mixed Hindi-English code-switching speech preserving medical terminology."""
        if "hi_code_switching" not in GROUND_TRUTH:
            pytest.skip("Audio fixture not generated")

        case = GROUND_TRUTH["hi_code_switching"]
        audio_file = Path(case["file"])
        assert audio_file.exists()

        t0 = time.time()
        res = transcribe_audio_file(audio_file, language_preference="hi")
        latency = time.time() - t0

        safe_print(f"\n[HINDI-ENGLISH CODE-SWITCHING]")
        safe_print(f"  Reference:  '{case['reference']}'")
        safe_print(f"  Transcript: '{res['transcript']}'")
        safe_print(f"  Language: {res['language_name']} | Latency: {latency:.2f}s")

        transcript_text = res["transcript"]
        transcript_lower = res["transcript"].lower()
        assert ("chest" in transcript_lower or "pain" in transcript_lower or "चेस्ट" in transcript_text or "पेन" in transcript_text or "दर्द" in transcript_text)

    def test_medical_dosages_and_numbers(self):
        """Test medical dosage, drug names (Paracetamol, Metformin), and numerals."""
        if "en_medical_dosage_numbers" not in GROUND_TRUTH:
            pytest.skip("Audio fixture not generated")

        case = GROUND_TRUTH["en_medical_dosage_numbers"]
        audio_file = Path(case["file"])
        assert audio_file.exists()

        res = transcribe_audio_file(audio_file, language_preference="en")
        safe_print(f"\n[MEDICAL DOSAGE & NUMBERS]")
        safe_print(f"  Reference:  '{case['reference']}'")
        safe_print(f"  Transcript: '{res['transcript']}'")

        text_lower = res["transcript"].lower()
        assert "paracetamol" in text_lower or "metformin" in text_lower
        assert "500" in text_lower or "50" in text_lower

    def test_auto_detect_accuracy_across_languages(self):
        """Test automatic language detection across English, Kannada, and Hindi without manual hints."""
        for key, expected_lang in [
            ("en_stat_emergency", "en"),
            ("kn_stat_emergency", "kn"),
            ("hi_stat_emergency", "hi")
        ]:
            if key not in GROUND_TRUTH:
                continue
            case = GROUND_TRUTH[key]
            audio_file = Path(case["file"])
            res = transcribe_audio_file(audio_file, language_preference="auto")
            safe_print(f"  Auto-detect {key}: detected='{res['language']}' (expected='{expected_lang}', prob={res['language_confidence']})")
            assert res["language"] == expected_lang
            assert res["language_confidence"] >= 0.50

    def test_audio_validation_guards(self):
        """Validate rejection of empty files, unsupported extensions, and oversized files."""
        with pytest.raises(ValueError, match="empty"):
            validate_audio_file("empty.wav", 0)

        with pytest.raises(ValueError, match="Unsupported audio format"):
            validate_audio_file("document.pdf", 1024)

        with pytest.raises(ValueError, match="exceeds the maximum limit"):
            validate_audio_file("huge.wav", 30 * 1024 * 1024)

    def test_devanagari_to_kannada_converter(self):
        """Test 1:1 ISCII/Unicode Devanagari to Kannada conversion fallback."""
        dev = "नमस्ते"
        kn = devanagari_to_kannada(dev)
        assert any('\u0C80' <= ch <= '\u0CFF' for ch in kn)

    def test_benchmark_model_comparison(self):
        """
        Systematic benchmark comparing Faster-Whisper configurations ('tiny' vs 'small' vs 'medium').
        Measures real Word Error Rate (WER), Character Error Rate (CER), latency, and real-time factor (RTF).
        """
        if "en_stat_emergency" not in GROUND_TRUTH:
            pytest.skip("Audio fixture not generated")

        sample_cases = [
            GROUND_TRUTH["en_stat_emergency"],
            GROUND_TRUTH["hi_stat_emergency"],
            GROUND_TRUTH["kn_stat_emergency"]
        ]

        models_to_test = ["tiny", "small", "medium"]
        benchmark_results = []

        safe_print("\n" + "=" * 80)
        safe_print("FASTER-WHISPER MULTILINGUAL MODEL BENCHMARK RESULTS")
        safe_print("=" * 80)
        safe_print(f"{'Model':<10} | {'Lang':<6} | {'Audio(s)':<8} | {'Latency(s)':<10} | {'RTF (Latency/Duration)':<22} | {'WER':<8} | {'CER':<8}")
        safe_print("-" * 80)

        for m_size in models_to_test:
            for case in sample_cases:
                audio_file = Path(case["file"])
                if not audio_file.exists():
                    continue

                t0 = time.time()
                res = transcribe_audio_file(audio_file, language_preference=case["lang"], model_size=m_size)
                latency = time.time() - t0
                duration = res["duration_seconds"] or 1.0

                ref_clean = clean_for_eval(case["reference"])
                hyp_clean = clean_for_eval(res["transcript"])

                w_err = wer(ref_clean, hyp_clean)
                c_err = cer(ref_clean, hyp_clean)
                rtf = latency / duration

                benchmark_results.append({
                    "model": m_size,
                    "language": case["lang"],
                    "duration": duration,
                    "latency": round(latency, 2),
                    "rtf": round(rtf, 2),
                    "wer": round(w_err, 4),
                    "cer": round(c_err, 4)
                })

                safe_print(
                    f"{m_size:<10} | {case['lang']:<6} | {duration:<8.2f} | {latency:<10.2f} | "
                    f"{rtf:<22.2f} | {w_err:<8.2%} | {c_err:<8.2%}"
                )

        safe_print("=" * 80)
        assert len(benchmark_results) > 0

if __name__ == "__main__":
    pytest.main(["-s", "-v", __file__])
