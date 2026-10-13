"""Audio validation and normalisation shared by every ASR provider.

Uploads are checked for size, extension, that the bytes really decode as audio, and the
duration cap *before* anything is queued.  Accepted audio is converted to 16 kHz, mono,
16-bit PCM WAV - the input format IndicConformer (and faster-whisper) expect.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import get_settings
from asr.base import InvalidAudio, AudioTooLong

logger = logging.getLogger("carerouter.asr.audio")

ALLOWED_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac"}
ALLOWED_MIME_PREFIXES = ("audio/", "video/webm", "application/octet-stream")
TARGET_SAMPLE_RATE = 16000


def validate_upload_metadata(filename: str, size: int, content_type: Optional[str]) -> None:
    """Cheap checks that need no decoding. Raises ``InvalidAudio`` with a user-safe message."""
    settings = get_settings()
    if size <= 0:
        raise InvalidAudio("The provided audio file is empty (0 bytes). Please record or upload a valid audio file.")
    max_bytes = settings.asr_max_upload_mb * 1024 * 1024
    if size > max_bytes:
        raise InvalidAudio(f"Audio file size exceeds the maximum limit of {settings.asr_max_upload_mb} MB.")
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidAudio(
            f"Unsupported audio format '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if content_type and not content_type.lower().startswith(ALLOWED_MIME_PREFIXES):
        raise InvalidAudio(f"Unsupported content type '{content_type}'.")


@dataclass
class PreparedAudio:
    wav_path: Path
    duration_seconds: float
    max_amplitude: float

    @property
    def is_silent(self) -> bool:
        return self.max_amplitude < 0.001


def prepare_audio(source: Path, dest_wav: Path) -> PreparedAudio:
    """Decode ``source`` and write a 16 kHz mono PCM WAV to ``dest_wav``.

    Raises ``InvalidAudio`` if the bytes are not decodable audio, ``AudioTooLong`` if the
    decoded length exceeds ASR_MAX_DURATION_SECONDS.
    """
    import av
    import numpy as np

    max_seconds = get_settings().asr_max_duration_seconds
    samples_written = 0
    max_amp = 0.0
    try:
        with av.open(str(source), mode="r", metadata_errors="ignore") as container:
            if not container.streams.audio:
                raise InvalidAudio("The file does not contain an audio stream.")
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="s16", layout="mono", rate=TARGET_SAMPLE_RATE)
            with av.open(str(dest_wav), mode="w", format="wav") as out:
                out_stream = out.add_stream("pcm_s16le", rate=TARGET_SAMPLE_RATE)
                out_stream.layout = "mono"

                def _write(resampled_frames):
                    nonlocal samples_written, max_amp
                    for rf in resampled_frames:
                        arr = rf.to_ndarray()
                        if arr.size:
                            max_amp = max(max_amp, float(np.max(np.abs(arr.astype("int32")))) / 32768.0)
                        samples_written += rf.samples
                        if samples_written / TARGET_SAMPLE_RATE > max_seconds:
                            raise AudioTooLong(
                                f"Audio is longer than the {max_seconds // 60} minute limit. "
                                "Please record a shorter clip."
                            )
                        for packet in out_stream.encode(rf):
                            out.mux(packet)

                for frame in container.decode(stream):
                    _write(resampler.resample(frame))
                _write(resampler.resample(None) or [])
                for packet in out_stream.encode():
                    out.mux(packet)
    except InvalidAudio:
        dest_wav.unlink(missing_ok=True)
        raise
    except Exception as exc:  # PyAV raises many distinct error types for corrupt input
        dest_wav.unlink(missing_ok=True)
        logger.info("Audio decode failed: %s", type(exc).__name__)
        raise InvalidAudio("The file could not be read as audio. It may be corrupted or not an audio recording.")

    if samples_written == 0:
        dest_wav.unlink(missing_ok=True)
        raise InvalidAudio("The audio file contains no audio samples.")
    return PreparedAudio(
        wav_path=dest_wav,
        duration_seconds=round(samples_written / TARGET_SAMPLE_RATE, 2),
        max_amplitude=round(max_amp, 4),
    )
