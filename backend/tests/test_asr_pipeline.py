"""Audio ingestion, background jobs, provider routing (IndicConformer / Whisper) and retention.

The real ASR models are never executed here; fake providers verify the application's behaviour
around them.  Whether IndicConformer *transcribes accurately* must be measured on the target host
(see docs/ASR_SETUP.md) - nothing in this file claims model accuracy.
"""
import json

import pytest

from asr import jobs as asr_jobs, service as asr_service
from asr.base import AsrError, ProviderUnavailable
from asr.indic_conformer_provider import IndicConformerProvider
from asr.languages import INDIC_CONFORMER_LANGUAGES, normalize_language
from models_care import AuditEvent, TranscriptionJob
from helpers import FakeProvider, make_wav

pytestmark = pytest.mark.real_auth


def upload(care, user, data, name="clip.wav", ctype="audio/wav", language=None, consent="true", retain=None):
    form = {"recording_consent": consent}
    if language is not None:
        form["language"] = language
    if retain is not None:
        form["retain_audio"] = retain
    return care.client.post("/api/audio/jobs", headers=user.headers, data=form, files={"audio_file": (name, data, ctype)})


def job(care, user, job_id):
    return care.client.get(f"/api/audio/jobs/{job_id}", headers=user.headers).json()


@pytest.fixture
def providers():
    whisper = FakeProvider("whisper", {"en", "hi", "kn"}, detect=True, text="patient akshay age 42 reports headache")
    indic = FakeProvider("indic_conformer", INDIC_CONFORMER_LANGUAGES, text="रोगी अक्षय उम्र 42")
    asr_service.register_provider(whisper)
    asr_service.register_provider(indic)
    return whisper, indic


# ---------------------------------------------------------------- upload validation
def test_empty_file_rejected(care):
    nurse = care.make_user("nurse")
    res = upload(care, nurse, b"")
    assert res.status_code == 400 and "empty" in res.json()["detail"].lower()


def test_wrong_extension_rejected(care):
    nurse = care.make_user("nurse")
    res = upload(care, nurse, b"hello", name="notes.txt", ctype="text/plain")
    assert res.status_code == 400 and "unsupported audio format" in res.json()["detail"].lower()


def test_wrong_content_type_rejected(care):
    nurse = care.make_user("nurse")
    res = upload(care, nurse, make_wav(), name="clip.wav", ctype="application/pdf")
    assert res.status_code == 400


def test_oversized_upload_rejected(care, monkeypatch):
    monkeypatch.setenv("ASR_MAX_UPLOAD_MB", "1")
    nurse = care.make_user("nurse")
    res = upload(care, nurse, b"\0" * (1024 * 1024 + 10))
    assert res.status_code == 400 and "maximum limit of 1 mb" in res.json()["detail"].lower()


def test_consent_is_mandatory_and_nothing_is_stored_without_it(care, tmp_path):
    nurse = care.make_user("nurse")
    res = upload(care, nurse, make_wav(), consent="false")
    assert res.status_code == 400 and "authorisation" in res.json()["detail"].lower()
    res = upload(care, nurse, make_wav(), consent="")
    assert res.status_code == 400
    with care.Session() as db:
        assert db.query(TranscriptionJob).count() == 0


def test_undecodable_audio_fails_the_job_with_clear_code(care, providers):
    nurse = care.make_user("nurse")
    res = upload(care, nurse, b"this is definitely not audio data " * 50)
    assert res.status_code == 202
    j = job(care, nurse, res.json()["job_id"])
    assert j["status"] == "failed" and j["error_code"] == "audio_invalid"
    assert j["audio_retained"] is False


def test_overlong_audio_rejected(care, providers, monkeypatch):
    monkeypatch.setenv("ASR_MAX_DURATION_SECONDS", "2")
    nurse = care.make_user("nurse")
    res = upload(care, nurse, make_wav(seconds=4))
    j = job(care, nurse, res.json()["job_id"])
    assert j["status"] == "failed" and j["error_code"] == "audio_too_long"


def test_silent_audio_reports_silence_without_running_the_model(care, providers):
    whisper, _ = providers
    nurse = care.make_user("nurse")
    res = upload(care, nurse, make_wav(amplitude=0.0), language="en")
    j = job(care, nurse, res.json()["job_id"])
    assert j["status"] == "succeeded" and j["result"]["is_silent"] is True and j["result"]["transcript"] == ""
    assert whisper.calls == []


# ---------------------------------------------------------------- success / failure
def test_successful_transcription_and_audio_is_deleted(care, providers):
    nurse = care.make_user("nurse")
    res = upload(care, nurse, make_wav(), language="en")
    assert res.status_code == 202
    j = job(care, nurse, res.json()["job_id"])
    assert j["status"] == "succeeded" and j["provider_used"] == "whisper"
    assert "akshay" in j["result"]["transcript"]
    assert j["audio_retained"] is False
    assert not list(asr_jobs.AUDIO_DIR.glob(f"*{res.json()['job_id']}*"))
    with care.Session() as db:
        stored = db.get(TranscriptionJob, res.json()["job_id"])
        assert stored.audio_path is None and stored.consent_confirmed is True


def test_provider_failure_reports_status_not_a_fake_transcript(care):
    asr_service.register_provider(FakeProvider("whisper", {"en"}, detect=True,
                                               fail=ProviderUnavailable("model files missing")))
    asr_service.register_provider(FakeProvider("indic_conformer", INDIC_CONFORMER_LANGUAGES, available=False))
    nurse = care.make_user("nurse")
    res = upload(care, nurse, make_wav(), language="en")
    j = job(care, nurse, res.json()["job_id"])
    assert j["status"] == "failed" and j["error_code"] == "asr_unavailable" and j["result"] is None


def test_unexpected_engine_crash_is_contained(care):
    asr_service.register_provider(FakeProvider("whisper", {"en"}, fail=RuntimeError("boom with PHI: John Doe")))
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav(), language="en").json()["job_id"])
    assert j["status"] == "failed" and j["error_code"] == "inference_failed"
    assert "John Doe" not in json.dumps(j)         # exception text is never echoed back


def test_jobs_are_private_to_the_requester(care, providers):
    a, b, admin = care.make_user("nurse"), care.make_user("nurse"), care.make_user("admin")
    job_id = upload(care, a, make_wav(), language="en").json()["job_id"]
    assert care.client.get(f"/api/audio/jobs/{job_id}", headers=b.headers).status_code == 404
    assert care.client.get(f"/api/audio/jobs/{job_id}", headers=admin.headers).status_code == 200


def test_job_runs_outside_the_request_via_executor(care, providers):
    """With a deferring executor the POST returns 'queued' before any inference happens."""
    class Deferred:
        def __init__(self):
            self.pending = []

        def submit(self, fn, *a):
            self.pending.append((fn, a))

    deferred = Deferred()
    asr_jobs.set_executor(deferred)
    whisper, _ = providers
    nurse = care.make_user("nurse")
    res = upload(care, nurse, make_wav(), language="en")
    assert res.status_code == 202 and res.json()["status"] == "queued"
    assert whisper.calls == []                           # nothing ran inside the request
    assert job(care, nurse, res.json()["job_id"])["status"] == "queued"
    fn, args = deferred.pending[0]
    fn(*args)
    assert job(care, nurse, res.json()["job_id"])["status"] == "succeeded"


def test_interrupted_jobs_are_failed_visibly_on_restart(care):
    nurse = care.make_user("nurse")
    with care.Session() as db:
        db.add(TranscriptionJob(id="a" * 32, requested_by_user_id=nurse.id, status="running", consent_confirmed=True))
        db.commit()
        assert asr_jobs.recover_interrupted_jobs(db) == 1
        j = db.get(TranscriptionJob, "a" * 32)
        assert j.status == "failed" and j.error_code == "interrupted"


# ---------------------------------------------------------------- multilingual routing
def test_indian_language_prefers_indic_conformer(care, providers):
    whisper, indic = providers
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav(), language="hi").json()["job_id"])
    assert j["provider_used"] == "indic_conformer" and indic.calls == ["hi"] and whisper.calls == []


def test_tamil_and_other_documented_languages_route_to_indic(care, providers):
    _, indic = providers
    nurse = care.make_user("nurse")
    for code in ("ta", "te", "bn", "mr", "ml"):
        j = job(care, nurse, upload(care, nurse, make_wav(), language=code).json()["job_id"])
        assert j["provider_used"] == "indic_conformer" and j["result"]["language"] == code
    assert indic.calls == ["ta", "te", "bn", "mr", "ml"]


def test_english_never_goes_to_indic_conformer(care, providers):
    whisper, indic = providers
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav(), language="en").json()["job_id"])
    assert j["provider_used"] == "whisper" and indic.calls == []
    assert "en" not in INDIC_CONFORMER_LANGUAGES


def test_falls_back_to_whisper_when_indic_is_unavailable(care):
    whisper = FakeProvider("whisper", {"en", "hi", "kn"}, detect=True)
    asr_service.register_provider(whisper)
    asr_service.register_provider(FakeProvider("indic_conformer", INDIC_CONFORMER_LANGUAGES, available=False))
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav(), language="kn").json()["job_id"])
    assert j["status"] == "succeeded" and j["provider_used"] == "whisper"
    assert any("preferred engine was unavailable" in w for w in j["result"]["warnings"])


def test_language_without_any_available_engine_is_reported(care):
    asr_service.register_provider(FakeProvider("whisper", {"en", "hi", "kn"}, detect=True))
    asr_service.register_provider(FakeProvider("indic_conformer", INDIC_CONFORMER_LANGUAGES, available=False))
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav(), language="ta").json()["job_id"])
    assert j["status"] == "failed" and j["error_code"] == "asr_unavailable"


def test_unsupported_language_is_not_silently_guessed(care, providers):
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav(), language="fr").json()["job_id"])
    assert j["status"] == "failed" and j["error_code"] == "unsupported_language"


def test_auto_detect_then_upgrade_to_indic_engine(care, providers):
    whisper, indic = providers
    whisper._detected = "hi"
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav(), language="auto").json()["job_id"])
    assert whisper.calls == [None] and indic.calls == ["hi"]
    assert j["provider_used"] == "indic_conformer"
    assert any("auto-detected" in w for w in j["result"]["warnings"])


def test_auto_detect_english_stays_on_whisper(care, providers):
    whisper, indic = providers
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav()).json()["job_id"])   # no language at all -> auto
    assert j["provider_used"] == "whisper" and indic.calls == []


def test_auto_detect_unavailable_asks_user_to_choose(care):
    asr_service.register_provider(FakeProvider("whisper", {"en"}, detect=True, available=False))
    asr_service.register_provider(FakeProvider("indic_conformer", INDIC_CONFORMER_LANGUAGES, available=True))
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav(), language="auto").json()["job_id"])
    assert j["status"] == "failed" and j["error_code"] == "unsupported_language"
    assert "select the spoken language" in j["error_message"].lower()


def test_failed_upgrade_keeps_first_pass_transcript(care, providers):
    whisper, indic = providers
    whisper._detected = "hi"
    indic._fail = AsrError("inference failed", code="inference_failed")
    nurse = care.make_user("nurse")
    j = job(care, nurse, upload(care, nurse, make_wav()).json()["job_id"])
    assert j["status"] == "succeeded" and j["provider_used"] == "whisper"
    assert any("failed for 'hi'" in w for w in j["result"]["warnings"])


def test_language_aliases_normalised():
    assert normalize_language("Hindi") == "hi" and normalize_language("AUTO") is None and normalize_language(None) is None
    assert normalize_language("Kannada") == "kn" and normalize_language("ta") == "ta"


def test_asr_status_endpoint_lists_real_availability(care, providers):
    nurse = care.make_user("nurse")
    body = care.client.get("/api/asr/status", headers=nurse.headers).json()
    names = {p["name"]: p for p in body["providers"]}
    assert set(names) == {"whisper", "indic_conformer"}
    langs = {entry["code"] for entry in body["languages"]}
    assert {"en", "hi", "kn", "ta", "te", "bn", "mr"} <= langs
    assert any("does not capture the other side" in n for n in body["notes"])


# ---------------------------------------------------------------- real IndicConformer adapter (no weights)
def test_real_indic_adapter_reports_unavailable_instead_of_faking(monkeypatch, tmp_path):
    monkeypatch.delenv("INDIC_ASR_ENABLED", raising=False)
    provider = IndicConformerProvider()
    ok, reason = provider.availability()
    assert not ok and "INDIC_ASR_ENABLED" in reason
    with pytest.raises(ProviderUnavailable):
        provider.transcribe(tmp_path / "x.wav", "hi")


def test_real_indic_adapter_requires_explicit_supported_language(monkeypatch, tmp_path):
    monkeypatch.setenv("INDIC_ASR_ENABLED", "true")
    provider = IndicConformerProvider()
    monkeypatch.setattr(provider, "availability", lambda: (True, ""))
    from asr.base import UnsupportedLanguage
    with pytest.raises(UnsupportedLanguage):
        provider.transcribe(tmp_path / "x.wav", None)         # no language identification
    with pytest.raises(UnsupportedLanguage):
        provider.transcribe(tmp_path / "x.wav", "en")         # English is not in the model


# ---------------------------------------------------------------- retention & authorisation
def test_retention_requires_deployment_opt_in(care, providers):
    nurse = care.make_user("nurse")
    res = upload(care, nurse, make_wav(), language="en", retain="true")
    assert res.status_code == 400 and "retention is disabled" in res.json()["detail"].lower()


def test_retained_audio_is_restricted_audited_and_purged(care, providers, monkeypatch):
    monkeypatch.setenv("AUDIO_RETENTION_HOURS", "1")
    nurse, clinician = care.make_user("nurse"), care.make_user("clinician")
    res = upload(care, nurse, make_wav(), language="en", retain="true")
    j = job(care, nurse, res.json()["job_id"])
    assert j["audio_retained"] is True
    with care.Session() as db:
        stored = db.get(TranscriptionJob, res.json()["job_id"])
        filename = stored.audio_path
        assert (asr_jobs.AUDIO_DIR / filename).exists()
    # nurses cannot play recordings back; clinicians can, and it is audited
    assert care.client.get(f"/api/audio/{filename}", headers=nurse.headers).status_code == 403
    assert care.client.get(f"/api/audio/{filename}", headers=clinician.headers).status_code == 200
    with care.Session() as db:
        assert db.query(AuditEvent).filter(AuditEvent.action == "audio_played").count() == 1
        # expire it and purge
        from datetime import datetime, timedelta
        stored = db.get(TranscriptionJob, res.json()["job_id"])
        stored.audio_delete_after = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
        assert asr_jobs.purge_expired_audio(db) == 1
        assert not (asr_jobs.AUDIO_DIR / filename).exists()


def test_sync_endpoint_also_requires_consent_and_keeps_no_audio(care, providers):
    nurse = care.make_user("nurse")
    files = {"audio_file": ("c.wav", make_wav(), "audio/wav")}
    assert care.client.post("/api/audio/transcribe", headers=nurse.headers, files=files, data={"language": "en"}).status_code == 400
    ok = care.client.post("/api/audio/transcribe", headers=nurse.headers, files=files,
                          data={"language": "en", "recording_consent": "true"})
    assert ok.status_code == 200 and ok.json()["audio_filename"] == ""


# ---------------------------------------------------------------- transcript correction flow
def test_reviewed_transcript_keeps_original_asr_text(care, providers):
    nurse = care.make_user("nurse")
    job_id = upload(care, nurse, make_wav(), language="en").json()["job_id"]
    asr_text = job(care, nurse, job_id)["result"]["transcript"]
    corrected = "Patient Akshay, age 42, reports a headache. Needs clinical assessment."
    res = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": corrected, "language": "en", "transcription_job_id": job_id,
        "source_channel": "microphone", "recording_consent": True})
    assert res.status_code == 200, res.text
    call = res.json()["call"]
    assert call["raw_transcript"] == corrected
    assert call["original_asr_transcript"] == asr_text
    assert call["transcript_edited"] is True and call["source_channel"] == "microphone"
    # someone else's job cannot be attached
    other = care.make_user("nurse")
    assert care.client.post("/api/calls/process-transcript", headers=other.headers, json={
        "raw_transcript": "Room 2 needs water.", "transcription_job_id": job_id}).status_code == 404
