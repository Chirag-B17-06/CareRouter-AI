"""Test helpers: synthetic audio and fake ASR providers. All data is fictional."""
import io
import math
import struct
import wave
from pathlib import Path
from typing import Optional, Tuple

from asr.base import AsrProvider, AsrResult, ProviderUnavailable, AsrError
from asr.languages import language_name


def make_wav(seconds: float = 1.0, freq: float = 440.0, amplitude: float = 0.3, rate: int = 16000,
             channels: int = 1) -> bytes:
    """A real, decodable WAV (sine tone). amplitude=0 gives a silent recording."""
    frames = int(seconds * rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(frames):
            v = int(amplitude * 32767 * math.sin(2 * math.pi * freq * i / rate))
            w.writeframes(struct.pack("<h", v) * channels)
    return buf.getvalue()


class FakeProvider(AsrProvider):
    """Deterministic stand-in for an ASR engine (the real models are not run in unit tests)."""

    def __init__(self, name: str, languages, *, detect: bool = False, available: bool = True,
                 text: str = "patient akshay age 42 reports headache", fail: Optional[Exception] = None,
                 detected: str = "en"):
        self.name = name
        self.supported_languages = frozenset(languages)
        self.supports_language_detection = detect
        self._available = available
        self._text = text
        self._fail = fail
        self._detected = detected
        self.calls = []

    def availability(self) -> Tuple[bool, str]:
        return (self._available, "" if self._available else "fake provider unavailable")

    def transcribe(self, wav_path: Path, language: Optional[str]) -> AsrResult:
        self.calls.append(language)
        assert Path(wav_path).exists()
        if self._fail:
            raise self._fail
        lang = language or self._detected
        return AsrResult(
            transcript=self._text, language=lang, language_name=language_name(lang),
            language_confidence=0.9 if not language else 1.0, transcription_confidence=0.8,
            duration_seconds=1.0, provider=self.name,
        )
