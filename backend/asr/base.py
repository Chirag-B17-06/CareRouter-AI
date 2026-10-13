"""Provider-neutral ASR types.

Anything that can turn a 16 kHz mono WAV file into text implements ``AsrProvider``; the
rest of the application only depends on this module, so engines can be swapped through
configuration (ASR_PROVIDER_ORDER) without touching routes, jobs or the UI.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


class AsrError(Exception):
    """Base class. ``code`` is a stable machine-readable value shown in job status."""
    code = "asr_error"

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        if code:
            self.code = code


class ProviderUnavailable(AsrError):
    code = "asr_unavailable"


class UnsupportedLanguage(AsrError):
    code = "unsupported_language"


class InvalidAudio(AsrError):
    code = "audio_invalid"


class AudioTooLong(InvalidAudio):
    code = "audio_too_long"


@dataclass
class AsrResult:
    transcript: str
    language: str                          # ISO-ish code, or "uncertain"
    language_name: str
    language_confidence: float
    transcription_confidence: float
    duration_seconds: float
    provider: str
    segments: List[Dict[str, Any]] = field(default_factory=list)
    is_silent: bool = False
    max_amplitude: float = 0.0
    language_uncertain: bool = False
    suggested_language: Optional[str] = None
    # False when the model does not expose a calibrated confidence (e.g. IndicConformer).
    confidence_available: bool = True
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AsrProvider(ABC):
    name: str = "base"
    #: Language codes this provider has been verified to handle.
    supported_languages: FrozenSet[str] = frozenset()
    #: True only if the provider can identify the spoken language itself.
    supports_language_detection: bool = False

    @abstractmethod
    def availability(self) -> Tuple[bool, str]:
        """(is_usable_now, human-readable reason when not)."""

    @abstractmethod
    def transcribe(self, wav_path: Path, language: Optional[str]) -> AsrResult:
        """Transcribe a normalised 16 kHz mono WAV. ``language=None`` requests detection."""

    def describe(self) -> Dict[str, Any]:
        ok, reason = self.availability()
        return {
            "name": self.name,
            "available": ok,
            "reason": "" if ok else reason,
            "languages": sorted(self.supported_languages),
            "language_detection": self.supports_language_detection,
        }
