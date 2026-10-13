"""Background transcription jobs.

Inference never runs inside the HTTP request.  ``submit_job`` validates and stores the
upload, creates a ``TranscriptionJob`` row and hands it to a small thread pool; clients poll
``GET /api/audio/jobs/{id}``.  For multi-instance deployments run the worker in its own
process/queue (the job row is the contract) - see docs/ASR_SETUP.md.

Privacy:
  * Recording consent must be affirmed on every submission.
  * Audio is deleted as soon as transcription finishes (success *or* failure) unless the
    caller explicitly asks to retain it AND the deployment has AUDIO_RETENTION_HOURS > 0.
  * Retained audio is only readable through an authenticated, audited endpoint and is purged
    after the retention window.
"""
import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.orm import Session

from audit import record_audit
from config import get_settings
from asr import service
from asr.audio import prepare_audio, validate_upload_metadata
from asr.base import AsrError, AsrResult, InvalidAudio
from asr.languages import normalize_language
from models_care import TranscriptionJob, utcnow

logger = logging.getLogger("carerouter.asr.jobs")

AUDIO_DIR = Path(__file__).resolve().parent.parent / "uploads"

# Session factory used by worker threads.  main.py points this at database.SessionLocal;
# tests point it at their in-memory engine.
session_factory: Optional[Callable[[], Session]] = None


class InlineExecutor:
    """Runs jobs synchronously. Used by tests; never in production."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


_executor = None
_executor_lock = threading.Lock()


def get_executor():
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=get_settings().asr_workers, thread_name_prefix="asr-worker"
            )
        return _executor


def set_executor(executor) -> None:
    global _executor
    _executor = executor


class JobRejected(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def submit_job(
    db: Session, *, user, data: bytes, filename: str, content_type: Optional[str],
    language: Optional[str], consent_confirmed: bool, retain_audio: bool = False,
) -> TranscriptionJob:
    settings = get_settings()
    try:
        validate_upload_metadata(filename, len(data), content_type)
    except InvalidAudio as exc:
        raise JobRejected(str(exc))
    if not consent_confirmed:
        raise JobRejected(
            "Recording authorisation is required. Confirm that the patient/caller has been informed "
            "and consents (or that policy permits) before audio is processed."
        )
    if retain_audio and settings.audio_retention_hours <= 0:
        raise JobRejected("Audio retention is disabled on this deployment.")
    lang = normalize_language(language)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    (AUDIO_DIR / stored_name).write_bytes(data)

    job = TranscriptionJob(
        id=uuid.uuid4().hex, requested_by_user_id=user.id, language_requested=lang, audio_path=stored_name,
        consent_confirmed=True, retain_audio=retain_audio, status="queued",
    )
    db.add(job)
    record_audit(db, user=user, action="audio_submitted", resource_type="transcription_job",
                 resource_id=job.id, detail={"retain_audio": retain_audio, "language": lang or "auto",
                                             "bytes": len(data)})
    db.commit()
    purge_expired_audio(db)
    get_executor().submit(run_job, job.id)
    return job


def _fail(job: TranscriptionJob, code: str, message: str) -> None:
    job.status = "failed"
    job.error_code = code
    job.error_message = message[:300]
    job.finished_at = utcnow()


def run_job(job_id: str) -> None:
    if session_factory is None:
        logger.error("ASR session_factory is not configured; job %s cannot run", job_id)
        return
    db = session_factory()
    src: Optional[Path] = None
    wav: Optional[Path] = None
    try:
        job = db.get(TranscriptionJob, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = utcnow()
        db.commit()

        src = AUDIO_DIR / job.audio_path
        wav = AUDIO_DIR / f"norm_{job.id}.wav"
        try:
            prepared = prepare_audio(src, wav)
            if prepared.is_silent:
                result = AsrResult(
                    transcript="", language=job.language_requested or "uncertain", language_name="",
                    language_confidence=0.0, transcription_confidence=0.0,
                    duration_seconds=prepared.duration_seconds, provider="none", is_silent=True,
                    max_amplitude=prepared.max_amplitude,
                    warnings=["The recording is silent. Check the microphone and try again."],
                )
            else:
                result = service.transcribe(prepared.wav_path, job.language_requested)
                result.duration_seconds = result.duration_seconds or prepared.duration_seconds
            job.provider_used = result.provider
            job.result_json = json.dumps(result.to_dict(), ensure_ascii=False)
            job.status = "succeeded"
            job.finished_at = utcnow()
        except AsrError as exc:
            _fail(job, exc.code, str(exc))
        except Exception as exc:
            logger.exception("Unexpected ASR failure for job %s (%s)", job_id, type(exc).__name__)
            _fail(job, "inference_failed", "Speech recognition failed unexpectedly. Please retry.")

        keep = job.status == "succeeded" and job.retain_audio
        if keep:
            job.audio_delete_after = utcnow() + timedelta(hours=get_settings().audio_retention_hours)
        else:
            job.audio_path = None
        db.commit()
        if not keep and src is not None:
            src.unlink(missing_ok=True)
    except Exception:
        logger.exception("ASR job %s crashed", job_id)
        db.rollback()
    finally:
        if wav is not None:
            wav.unlink(missing_ok=True)
        db.close()


def purge_expired_audio(db: Session) -> int:
    """Delete retained audio past its retention window. Returns files removed."""
    now = utcnow()
    removed = 0
    expired = (
        db.query(TranscriptionJob)
        .filter(TranscriptionJob.audio_path.isnot(None), TranscriptionJob.audio_delete_after.isnot(None),
                TranscriptionJob.audio_delete_after <= now.replace(tzinfo=None))
        .all()
    )
    for job in expired:
        (AUDIO_DIR / job.audio_path).unlink(missing_ok=True)
        job.audio_path = None
        removed += 1
    if removed:
        db.commit()
    return removed


def recover_interrupted_jobs(db: Session) -> int:
    """Jobs left queued/running by a crash or restart can never finish - fail them visibly."""
    stuck = db.query(TranscriptionJob).filter(TranscriptionJob.status.in_(("queued", "running"))).all()
    for job in stuck:
        _fail(job, "interrupted", "The server restarted before transcription finished. Please resubmit the audio.")
        if job.audio_path:
            (AUDIO_DIR / job.audio_path).unlink(missing_ok=True)
            job.audio_path = None
    if stuck:
        db.commit()
    return len(stuck)
