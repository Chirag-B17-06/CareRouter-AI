"""faster-whisper adapter (the engine the project already shipped with)."""
from pathlib import Path
from typing import Optional, Tuple

from asr.base import AsrProvider, AsrResult, ProviderUnavailable, UnsupportedLanguage
from asr.languages import language_name


class WhisperProvider(AsrProvider):
    name = "whisper"
    # Languages exercised by this project's existing pipeline and tests. Whisper itself
    # knows more, but we only claim what has been verified here.
    supported_languages = frozenset({"en", "hi", "kn"})
    supports_language_detection = True

    def availability(self) -> Tuple[bool, str]:
        try:
            import faster_whisper  # noqa: F401
        except Exception:
            return False, "faster-whisper is not installed (pip install faster-whisper)"
        return True, ""

    def transcribe(self, wav_path: Path, language: Optional[str]) -> AsrResult:
        if language and language not in self.supported_languages:
            raise UnsupportedLanguage(f"Whisper pipeline is configured for en/hi/kn only, not '{language}'.")
        ok, reason = self.availability()
        if not ok:
            raise ProviderUnavailable(reason)
        from audio_transcriber import transcribe_audio_file  # heavy import, deferred

        raw = transcribe_audio_file(wav_path, language_preference=language)
        lang = raw["language"]
        return AsrResult(
            transcript=raw["transcript"],
            language=lang,
            language_name=raw.get("language_name") or language_name(lang),
            language_confidence=raw["language_confidence"],
            transcription_confidence=raw["transcription_confidence"],
            duration_seconds=raw["duration_seconds"],
            provider=self.name,
            segments=raw.get("segments", []),
            is_silent=raw.get("is_silent", False),
            max_amplitude=raw.get("max_amplitude", 0.0),
            language_uncertain=raw.get("language_uncertain", False),
            suggested_language=raw.get("suggested_language"),
        )
