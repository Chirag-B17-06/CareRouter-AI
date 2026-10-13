"""AI4Bharat IndicConformer adapter.

Source of truth for the interface used here (verified against the public model card for
``ai4bharat/indic-conformer-600m-multilingual``, MIT licence):

    model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True)
    text  = model(wav, "<lang>", "ctc" | "rnnt")      # wav: float tensor, shape (1, T), 16 kHz mono

Facts that shape this adapter:
  * The multilingual checkpoint covers 22 Indian languages and does NOT include English.
  * The caller must supply the language code - the model does no language identification.
  * The repository is gated on Hugging Face: accept the terms and provide a token
    (HF_TOKEN) before the first download.
  * ``trust_remote_code=True`` executes code from the model repository.  Pin a reviewed
    revision with INDIC_ASR_MODEL_REVISION in production.
  * The model exposes no calibrated per-utterance confidence, so none is reported.

This adapter has NOT been executed against the real weights in this repository's test run
(the weights are gated and large).  See docs/ASR_SETUP.md for the validation steps to run on
the target host.
"""
import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional, Tuple

from config import get_settings
from asr.base import AsrProvider, AsrResult, ProviderUnavailable, UnsupportedLanguage, AsrError
from asr.languages import INDIC_CONFORMER_LANGUAGES, language_name

logger = logging.getLogger("carerouter.asr.indic")


class IndicConformerProvider(AsrProvider):
    name = "indic_conformer"
    supported_languages = INDIC_CONFORMER_LANGUAGES
    supports_language_detection = False

    def __init__(self):
        self._model: Any = None
        self._lock = threading.Lock()

    def availability(self) -> Tuple[bool, str]:
        settings = get_settings()
        if not settings.indic_asr_enabled:
            return False, "Disabled (set INDIC_ASR_ENABLED=true after installing the model dependencies)"
        missing = []
        for module in ("torch", "torchaudio", "transformers"):
            try:
                __import__(module)
            except Exception:
                missing.append(module)
        if missing:
            return False, "Missing Python packages: " + ", ".join(missing) + " (see docs/ASR_SETUP.md)"
        return True, ""

    def _load(self):
        with self._lock:
            if self._model is None:
                from transformers import AutoModel

                settings = get_settings()
                kwargs = {"trust_remote_code": True}
                revision = os.getenv("INDIC_ASR_MODEL_REVISION")
                if revision:
                    kwargs["revision"] = revision
                logger.info("Loading IndicConformer model (first use; may download weights)")
                try:
                    self._model = AutoModel.from_pretrained(settings.indic_asr_model_id, **kwargs)
                except Exception as exc:
                    raise ProviderUnavailable(
                        "IndicConformer model could not be loaded. Check HF_TOKEN / gated-access approval, "
                        f"network access and disk space. ({type(exc).__name__})"
                    )
            return self._model

    def transcribe(self, wav_path: Path, language: Optional[str]) -> AsrResult:
        ok, reason = self.availability()
        if not ok:
            raise ProviderUnavailable(reason)
        if not language:
            raise UnsupportedLanguage("IndicConformer cannot detect the language; select one explicitly.")
        if language not in self.supported_languages:
            raise UnsupportedLanguage(f"IndicConformer does not support '{language}'.")

        decoding = get_settings().indic_asr_decoding
        if decoding not in ("ctc", "rnnt"):
            raise AsrError(f"INDIC_ASR_DECODING must be 'ctc' or 'rnnt', got '{decoding}'", code="config_error")

        import torch
        import torchaudio

        model = self._load()
        wav, sr = torchaudio.load(str(wav_path))
        wav = torch.mean(wav, dim=0, keepdim=True)           # mono
        if sr != 16000:                                       # normally a no-op: input is pre-normalised
            wav = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)(wav)
        try:
            with torch.inference_mode():
                text = model(wav, language, decoding)
        except Exception as exc:
            raise AsrError(f"IndicConformer inference failed ({type(exc).__name__})", code="inference_failed")
        if isinstance(text, (list, tuple)):
            text = " ".join(str(t) for t in text)
        text = (text or "").strip()
        duration = round(wav.shape[1] / 16000, 2)
        return AsrResult(
            transcript=text,
            language=language,
            language_name=language_name(language),
            language_confidence=1.0,           # caller-specified, not detected
            transcription_confidence=0.0,
            confidence_available=False,
            duration_seconds=duration,
            provider=self.name,
            warnings=[
                "Language was selected by the user; IndicConformer does not verify it.",
                "No model confidence is available. English words inside Indian-language speech may be "
                "transliterated or dropped; review the transcript before submitting.",
            ],
        )
