"""Provider selection.

Routing rules (all configurable through ASR_PROVIDER_ORDER / INDIC_ASR_ENABLED):

* A language was chosen -> the first *available* provider in the configured order that
  supports it.  English therefore goes to Whisper even when IndicConformer is enabled,
  because the IndicConformer checkpoint does not cover English.
* Auto-detect -> a provider that can identify language does a first pass.  If the detected
  language is one a higher-priority, available provider supports, that provider re-runs
  the audio with the detected code.  If the re-run fails, the first-pass transcript is
  returned with a warning rather than failing the request.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

from config import get_settings
from asr.base import (
    AsrProvider, AsrResult, AsrError, ProviderUnavailable, UnsupportedLanguage,
)
from asr.languages import normalize_language, language_name
from asr.indic_conformer_provider import IndicConformerProvider
from asr.whisper_provider import WhisperProvider

logger = logging.getLogger("carerouter.asr.service")

_registry: Dict[str, AsrProvider] = {}


def _ensure_defaults() -> None:
    if not _registry:
        for provider in (IndicConformerProvider(), WhisperProvider()):
            _registry[provider.name] = provider


def register_provider(provider: AsrProvider) -> None:
    """Add or replace a provider (new engines, or fakes in tests)."""
    _ensure_defaults()
    _registry[provider.name] = provider


def reset_registry() -> None:
    _registry.clear()


def ordered_providers() -> List[AsrProvider]:
    _ensure_defaults()
    order = get_settings().asr_provider_order
    named = [_registry[n] for n in order if n in _registry]
    extras = [p for n, p in _registry.items() if n not in order]
    return named + extras


def describe_providers() -> List[dict]:
    return [p.describe() for p in ordered_providers()]


def supported_language_catalog() -> List[dict]:
    """Languages a user can select right now, given what is actually available."""
    catalog: Dict[str, dict] = {}
    for provider in ordered_providers():
        ok, _ = provider.availability()
        for code in sorted(provider.supported_languages):
            entry = catalog.setdefault(code, {"code": code, "name": language_name(code), "providers": []})
            entry["providers"].append({"name": provider.name, "available": ok})
    for entry in catalog.values():
        entry["available"] = any(p["available"] for p in entry["providers"])
    return sorted(catalog.values(), key=lambda e: (not e["available"], e["name"]))


def transcribe(wav_path: Path, language: Optional[str]) -> AsrResult:
    lang = normalize_language(language)
    providers = ordered_providers()

    if lang:
        capable = [p for p in providers if lang in p.supported_languages]
        if not capable:
            raise UnsupportedLanguage(
                f"No configured speech engine supports language '{lang}'. "
                "Choose a supported language or leave language on auto-detect for English/Hindi/Kannada."
            )
        problems: List[str] = []
        for index, provider in enumerate(capable):
            ok, reason = provider.availability()
            if not ok:
                problems.append(f"{provider.name}: {reason}")
                continue
            try:
                result = provider.transcribe(wav_path, lang)
            except ProviderUnavailable as exc:
                problems.append(f"{provider.name}: {exc}")
                continue
            if index > 0 or problems:
                result.warnings.append(f"Used '{provider.name}' because a preferred engine was unavailable.")
            return result
        raise ProviderUnavailable("No speech engine is currently available for this language. " + "; ".join(problems))

    detectors = [p for p in providers if p.supports_language_detection and p.availability()[0]]
    if not detectors:
        raise UnsupportedLanguage(
            "Automatic language detection is not available. Please select the spoken language."
        )
    first = detectors[0].transcribe(wav_path, None)
    detected = first.language
    if first.is_silent or first.language_uncertain or detected not in {c for p in providers for c in p.supported_languages}:
        return first

    for provider in providers:
        if provider.name == first.provider:
            break  # only providers ranked above the detector are considered an upgrade
        if detected in provider.supported_languages and provider.availability()[0]:
            try:
                upgraded = provider.transcribe(wav_path, detected)
                upgraded.language_confidence = first.language_confidence
                upgraded.language_uncertain = first.language_uncertain
                upgraded.warnings.append(
                    f"Language auto-detected as '{detected}' by '{first.provider}' (confidence {first.language_confidence:.2f}) "
                    f"and transcribed with '{provider.name}'."
                )
                return upgraded
            except AsrError as exc:
                first.warnings.append(f"'{provider.name}' failed for '{detected}' ({exc.code}); showing '{first.provider}' output.")
                break
    return first
