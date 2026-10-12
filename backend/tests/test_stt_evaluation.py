import os
import sys
import io
import time
from pathlib import Path
import pytest
from jiwer import wer, cer

# Setup NVIDIA DLL paths on Windows
prefix_path = Path(sys.prefix)
for bin_dir in prefix_path.glob("Lib/site-packages/nvidia/*/bin"):
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
    get_whisper_model, get_engine_status, devanagari_to_kannada
)

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"

# --- Reference Test Cases ---
AUDIO_TEST_CASES = {
    # 1. Clear Spoken English
    "en_chest_pain": {
        "file": UPLOADS_DIR / "03c405cb02c04aa5a1b9d22bbf9d2da2.webm",
        "lang": "en",
        "reference": "I have chest pain."
    },
    "en_no_pain": {
        "file": UPLOADS_DIR / "3de5521927d0482fa24912e9c03f77f9.webm",
        "lang": "en",
        "reference": "I don't have any pain."
    },
    # 2. Clear Spoken Kannada (Native Script)
    "kn_chest_pain_1": {
        "file": UPLOADS_DIR / "3afd4df0102f4d4f9d6a5e6fff08ec78.wav",
        "lang": "kn",
        "reference": "ನನಗೆ ಎದೆ ನೋವು ಇದೆ."
    },
    "kn_chest_pain_2": {
        "file": UPLOADS_DIR / "6749ae7f92844519991fd0b502b0d492.webm",
        "lang": "kn",
        "reference": "ನನಗೆ ಎದೆ ನೋವು ಇದೆ."
    },
    # 3. Clear Spoken Hindi (Devanagari Script)
    "hi_chest_pain": {
        "file": UPLOADS_DIR / "69ff27ae210242729651d37b7c6848db.wav",
        "lang": "hi",
        "reference": "मुझे सीने में दर्द हो रहा है।"
    },
    # 4. Mixed Hindi-English Code Switching
    "hi_en_mixed": {
        "file": UPLOADS_DIR / "1a97cf8c68ac42038a8aca55dbb2df8e.webm",
        "lang": "hi",
        "reference": "मेरा नाम चिराग है और मुझे बहुत चेस्ट में पेन हो रहा है और स्वेलिंग इनसाइड"
    }
}

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
    import re
    cleaned = re.sub(r'[^\w\s\u0C80-\u0CFF\u0900-\u097F]', '', text)
    return " ".join(cleaned.split()).lower()

class TestSTTEngine:

    def test_engine_initialization_and_device(self):
        """Verify model loads as singleton and reports GPU/CPU acceleration status."""
        model = get_whisper_model()
        assert model is not None
        status = get_engine_status()
        assert status["engine"] == "faster-whisper"
        assert status["is_loaded"] is True
        safe_print(f"\n[ENGINE STATUS] Device: {status['device'].upper()} | Compute: {status['compute_type']} | Model: {status['model_size']}")

    def test_english_transcription_accuracy(self):
        """Test English transcription accuracy and measure WER/CER."""
        case = AUDIO_TEST_CASES["en_chest_pain"]
        if not case["file"].exists():
            pytest.skip("Audio sample not present")

        t0 = time.time()
        res = transcribe_audio_file(case["file"], language_preference="en")
        latency = time.time() - t0

        ref_clean = clean_for_eval(case["reference"])
        hyp_clean = clean_for_eval(res["transcript"])

        w_err = wer(ref_clean, hyp_clean)
        c_err = cer(ref_clean, hyp_clean)

        safe_print(f"\n[ENGLISH ACCURACY]")
        safe_print(f"  Reference:  '{case['reference']}'")
        safe_print(f"  Transcript: '{res['transcript']}'")
        safe_print(f"  WER: {w_err:.2%} | CER: {c_err:.2%} | Latency: {latency:.2f}s")

        assert res["language"] == "en"
        assert "chest pain" in res["transcript"].lower()
        assert w_err == 0.0

    def test_kannada_transcription_accuracy(self):
        """Test Kannada transcription in native Kannada script and measure WER/CER."""
        case = AUDIO_TEST_CASES["kn_chest_pain_1"]
        if not case["file"].exists():
            pytest.skip("Audio sample not present")

        t0 = time.time()
        res = transcribe_audio_file(case["file"], language_preference="kn")
        latency = time.time() - t0

        ref_clean = clean_for_eval(case["reference"])
        hyp_clean = clean_for_eval(res["transcript"])

        w_err = wer(ref_clean, hyp_clean)
        c_err = cer(ref_clean, hyp_clean)

        safe_print(f"\n[KANNADA ACCURACY]")
        safe_print(f"  Reference:  '{case['reference']}'")
        safe_print(f"  Transcript: '{res['transcript']}'")
        safe_print(f"  WER: {w_err:.2%} | CER: {c_err:.2%} | Latency: {latency:.2f}s")

        assert res["language"] == "kn"
        # Must contain native Kannada script characters (0x0C80 to 0x0CFF)
        assert any('\u0C80' <= ch <= '\u0CFF' for ch in res["transcript"])
        assert "ನೋವು" in res["transcript"]
        assert w_err <= 0.15

    def test_hindi_transcription_accuracy(self):
        """Test Hindi transcription in Devanagari script and measure WER/CER."""
        case = AUDIO_TEST_CASES["hi_chest_pain"]
        if not case["file"].exists():
            pytest.skip("Audio sample not present")

        t0 = time.time()
        res = transcribe_audio_file(case["file"], language_preference="hi")
        latency = time.time() - t0

        ref_clean = clean_for_eval(case["reference"])
        hyp_clean = clean_for_eval(res["transcript"])

        w_err = wer(ref_clean, hyp_clean)
        c_err = cer(ref_clean, hyp_clean)

        safe_print(f"\n[HINDI ACCURACY]")
        safe_print(f"  Reference:  '{case['reference']}'")
        safe_print(f"  Transcript: '{res['transcript']}'")
        safe_print(f"  WER: {w_err:.2%} | CER: {c_err:.2%} | Latency: {latency:.2f}s")

        assert res["language"] == "hi"
        # Must contain Devanagari characters (0x0900 to 0x097F)
        assert any('\u0900' <= ch <= '\u097F' for ch in res["transcript"])
        assert "दर्द" in res["transcript"]
        assert w_err <= 0.20

    def test_hindi_english_code_switching(self):
        """Test Hindi-English mixed clinical speech preserving spoken terminology."""
        case = AUDIO_TEST_CASES["hi_en_mixed"]
        if not case["file"].exists():
            pytest.skip("Audio sample not present")

        t0 = time.time()
        res = transcribe_audio_file(case["file"], language_preference="hi")
        latency = time.time() - t0

        safe_print(f"\n[HINDI-ENGLISH MIXED CODE-SWITCHING]")
        safe_print(f"  Transcript: '{res['transcript']}'")
        safe_print(f"  Language: {res['language_name']} | Latency: {latency:.2f}s")

        assert res["language"] == "hi"
        # Verify clinical terms are captured in Devanagari or English
        transcript_text = res["transcript"]
        assert ("चेस्ट" in transcript_text or "chest" in transcript_text.lower())
        assert ("पेइन" in transcript_text or "दर्द" in transcript_text or "पेन" in transcript_text)

    def test_auto_detect_kannada_and_uncertainty(self):
        """Test auto-detection and graceful uncertainty flagging for ambiguous audio."""
        case = AUDIO_TEST_CASES["kn_chest_pain_2"]
        if not case["file"].exists():
            pytest.skip("Audio sample not present")

        res = transcribe_audio_file(case["file"], language_preference="auto")
        safe_print(f"\n[AUTO DETECT KANNADA]")
        safe_print(f"  Reported Language: {res['language']} (Uncertain={res['language_uncertain']})")
        safe_print(f"  Transcript: '{res['transcript']}'")

        # Either correctly detected as kn with high probability or flagged as uncertain with suggested language
        if res["language"] == "kn":
            assert res["language_confidence"] >= 0.80
        else:
            assert res["language_uncertain"] is True
            assert res["suggested_language"] in {"kn", "en", "hi"}

    def test_empty_audio_rejection(self):
        """Empty audio (0 bytes) must raise a clear ValueError."""
        with pytest.raises(ValueError, match="empty"):
            validate_audio_file("empty.wav", 0)

    def test_unsupported_format_rejection(self):
        """Unsupported extensions must raise a clear ValueError."""
        with pytest.raises(ValueError, match="Unsupported audio format"):
            validate_audio_file("document.pdf", 1024)

    def test_oversized_audio_rejection(self):
        """Files exceeding 25MB limit must be rejected."""
        with pytest.raises(ValueError, match="exceeds the maximum limit"):
            validate_audio_file("huge.wav", 30 * 1024 * 1024)

    def test_devanagari_to_kannada_converter(self):
        """Test ISCII Unicode transliteration fallback."""
        dev = "नमस्ते"
        kn = devanagari_to_kannada(dev)
        assert any('\u0C80' <= ch <= '\u0CFF' for ch in kn)

if __name__ == "__main__":
    pytest.main(["-s", "-v", __file__])
