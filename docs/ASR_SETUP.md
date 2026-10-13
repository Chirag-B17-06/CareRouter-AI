# Speech-to-text setup (Whisper + AI4Bharat IndicConformer)

CareRouter AI transcribes on the **server**. The browser only captures audio and sends it over the
authenticated API; no model runs in the browser.

```
browser mic / upload ──► POST /api/audio/jobs (auth + consent + size/type checks)
                              │  returns 202 + job id immediately
                              ▼
                     background worker (ThreadPoolExecutor, ASR_WORKERS)
                       decode → 16 kHz mono PCM WAV → provider routing
                              │
                              ▼
        GET /api/audio/jobs/{id}  ◄── browser polls: queued → running → succeeded | failed
```

Inference never runs inside the HTTP request. Audio is deleted as soon as a job finishes (success or
failure) unless retention is explicitly enabled (see *Privacy* below).

## Engines and what is actually verified

| Engine | Languages claimed by this app | Language detection | Status in this repo |
|---|---|---|---|
| `whisper` (faster-whisper, existing) | English, Hindi, Kannada | yes | Runs locally; used in the live smoke test |
| `indic_conformer` (AI4Bharat) | the 22 codes on the model card (below) | **no** – you must pick the language | **Adapter written, not executed against the real weights here** (gated, ~GB-scale). Follow *Validate on your host* before relying on it |

**Facts taken from the official sources** (GitHub `AI4Bharat/IndicConformerASR` and the Hugging Face
card for `ai4bharat/indic-conformer-600m-multilingual`, MIT licence, checked October 2026):

* Languages: `as bn brx doi gu hi kn kok ks mai ml mni mr ne or pa sa sat sd ta te ur`.
  **English is not supported by this model.** Mixed English/Indian-language speech is therefore not
  something this model is documented to handle; expect English words to be transliterated or missed.
* Interface: `AutoModel.from_pretrained(<id>, trust_remote_code=True)`, then
  `model(wav, "<lang>", "ctc" | "rnnt")` with `wav` a float tensor `(1, T)` at 16 kHz, mono.
* The repository is **gated** on Hugging Face: accept the terms and provide a token (`HF_TOKEN`).
* It runs code from the model repository (`trust_remote_code=True`). Pin a reviewed commit with
  `INDIC_ASR_MODEL_REVISION`.
* The model card publishes a single evaluation (Hindi WER 13.2 on Vaani-Benchmark-V1.0) and says
  nothing about clinical vocabulary, accents, noise or code-mixing. No model confidence is exposed, so
  the app shows "confidence not provided" instead of inventing one.
* The card also points to a newer model (*Indic-Transcribe*, 25 languages). To adopt a different
  model, implement `AsrProvider` (see *Replacing the model*).

### Routing rules

* A language chosen in the UI → the first **available** engine (order from `ASR_PROVIDER_ORDER`) that
  supports it. English therefore always uses Whisper, even when IndicConformer is enabled.
* If the preferred engine is unavailable, the next capable engine is used and the result carries a
  warning ("Used 'whisper' because a preferred engine was unavailable").
* Auto-detect → Whisper identifies the language; if that language is covered by a higher-priority
  available engine, the audio is re-run with it. A failed re-run falls back to the first-pass text
  with a warning rather than failing.
* Unsupported language, or auto-detect with no detector available → a clear `unsupported_language`
  error. The app never guesses.
* `GET /api/asr/status` reports which engines and languages are usable *right now*; the language picker
  is built from it.

## Installing IndicConformer (optional)

Run on the host that will serve it (a GPU is strongly preferred; the 600M model is slow on CPU).

```bash
# 1) Install a torch/torchaudio build for your hardware first: https://pytorch.org/get-started/locally/
cd backend
venv\Scripts\activate            # or: source venv/bin/activate
pip install -r requirements-indic.txt
#    GPU hosts: pip uninstall onnxruntime && pip install onnxruntime-gpu==1.20.1

# 2) Accept the model terms while signed in at
#    https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual
#    then create a read token and export it (never commit it):
set HF_TOKEN=<your token>

# 3) Enable it
set INDIC_ASR_ENABLED=true
set INDIC_ASR_DECODING=ctc       # or rnnt
set INDIC_ASR_MODEL_REVISION=<reviewed commit sha>
uvicorn main:app --host 127.0.0.1 --port 8000
```

Weights download on first use into the Hugging Face cache (outside the repository; nothing large is
version-controlled). `GET /api/asr/status` will show `indic_conformer` as available once the packages
import and the flag is on; a failed model load is reported per job as `asr_unavailable`.

The AI4Bharat README additionally documents installing their NeMo fork for training/fine-tuning;
that is **not** required for the Hugging Face inference path used here.

### Validate on your host (do this before clinical use)

1. `python -c "import torch, torchaudio, transformers; print(torch.__version__)"` succeeds.
2. Upload a short, consented, *fictional* recording in Hindi/Kannada/Tamil through the UI with that
   language selected; confirm `provider_used = indic_conformer` in `GET /api/audio/jobs/{id}`.
3. Measure word error rate on a labelled set of your own call audio (the repo ships `jiwer` and
   `backend/tests/test_stt_evaluation.py` as a starting point; its fixtures must be generated on your
   machine). Do not rely on the published Hindi figure for your accents, rooms and vocabulary.
4. Decide a minimum quality bar and keep human transcript review mandatory regardless.

## Resource and abuse limits (all environment-configurable)

| Variable | Default | Purpose |
|---|---|---|
| `ASR_MAX_UPLOAD_MB` | 25 | Upload size cap (bounded read; larger bodies are never fully buffered) |
| `ASR_MAX_DURATION_SECONDS` | 600 | Decoded length cap, enforced while decoding |
| `ASR_WORKERS` | 1 | Concurrent transcription jobs in this process |
| `RATE_LIMIT_PER_MINUTE` | 120 | Per-client request cap (login has its own stricter cap) |
| `ASR_PROVIDER_ORDER` | `indic_conformer,whisper` | Engine preference |

Accepted types: `.wav .webm .mp3 .m4a .ogg .flac .aac`, checked by extension, content type **and** by
actually decoding the audio.

## Privacy

* `recording_consent=true` is required on every upload; the UI blocks the microphone until the nurse
  confirms authorisation, and the server rejects uploads without it.
* `AUDIO_RETENTION_HOURS=0` (default): audio is deleted immediately after transcription. Setting it
  above 0 only *allows* users to opt in per upload; retained audio is playable only by roles with
  `audio:read` (admin, clinician), every playback is audited, and files are purged after the window
  (`python manage.py purge-audio`, also run at startup and on each upload).
* Transcripts are stored with the conversation (they are the clinical communication record). They are
  never written to application logs; errors returned to clients never echo transcript text.
* **Phone audio:** the browser microphone captures only sound near the computer. It does **not**
  capture the remote caller on a separate phone line. Capturing both sides requires a telephony
  integration (SIP/CTI recording, cloud-contact-centre media streams, or a call-recording system) that
  hands audio to `POST /api/audio/jobs`. None is bundled, and none is claimed.

## Scaling out

The job row (`transcription_jobs`) is the contract between API and worker. For several API instances,
run workers as a separate process or queue consumer that calls `asr.jobs.run_job(job_id)` with a shared
database and shared private audio storage, and put rate limiting at the gateway (the built-in limiter
is per-process). `asr.jobs.recover_interrupted_jobs` marks jobs orphaned by a restart as failed so
users can resubmit instead of waiting forever.

## Replacing the model

Implement `asr.base.AsrProvider` (`availability()`, `transcribe(wav_path, language)`, a language set and
whether it can detect language), register it with `asr.service.register_provider(...)` (or add it to the
default list in `asr/service.py`), and add its name to `ASR_PROVIDER_ORDER`. Routes, jobs, the UI and
the tests need no changes.
