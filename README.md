# CareRouter AI 🏥🎙️

> **Conversation-to-action and patient-coordination platform for hospitals.**
> Turns nurse-spoken summaries, authorised recordings, uploaded audio and typed notes into reviewed,
> structured records and routed tasks — and lets patients book and manage appointments.

It is **decision support, not a clinician**: it never diagnoses, never creates prescriptions, never
auto-links a conversation to a medical record, and never lets a queue delay an emergency.

---

## What it does

| Area | Capability |
|---|---|
| **Nurse workstation** | Consent gate → microphone / upload / typed entry → near-live transcript → editable review → structured extraction → task creation. Clear language, recording, loading, error and retry states |
| **Speech-to-text** | Server-side, background jobs. `faster-whisper` (English/Hindi/Kannada, language detection) plus an adapter for **AI4Bharat IndicConformer** (22 Indian languages, language must be chosen). See [docs/ASR_SETUP.md](docs/ASR_SETUP.md) |
| **Extraction** | Strict schema, grounded against the transcript (names, ages, ids, medicines and quotes must literally appear). Negation preserved; hedged diagnoses stay *unverified*; missing data is `null`. Offline rules by default; optional LLM adapter (off unless explicitly authorised) with the rule engine as an emergency safety floor |
| **Patients** | Profiles with opaque ids, fuzzy duplicate detection, **human-confirmed** conversation linking, clinician-entered clinical records, immutable verified prescriptions (changes supersede, history kept) |
| **Tasks & routing** | Many tasks per conversation, 9 statuses, due dates/overdue, reassignment, escalation, per-task audit trail. Configurable routing rules + SLA policy + fallback queue; every task records *why* it went where it did |
| **Appointments** | Staff-defined slots only (nothing invented), atomic double-booking protection, hospital-timezone aware, change requests, reminders/confirmations outbox, approved follow-up instructions |
| **Patient portal** | Patient accounts see only their own data: book/reschedule/cancel requests, upcoming & past, routine requests with status, updates |
| **Dashboard** | Triage board by team, review queue, overdue/unacknowledged/escalated filters, appointments overview, shift handover, analytics, admin routing + audit views |
| **Security** | Role-based access enforced server-side, signed sessions, lockout + rate limits, hash-chained audit log, PHI-free logs |

---

## Architecture

```
React 19 + Vite + Tailwind  ──HTTPS/JWT──►  FastAPI (Python)  ──►  SQLite via SQLAlchemy (any SQL DB)
 staff app │ patient portal                   auth · RBAC · audit · rate limit
                                              asr/        providers + job runner
                                              extraction/ schema · rules · llm
                                              routing · patients · scheduling · tasks_service
```

New backend modules: `config.py`, `auth.py`, `audit.py`, `ratelimit.py`, `models_care.py`, `migrations.py`,
`routing.py`, `patients.py`, `patient_matching.py`, `scheduling.py`, `tasks_service.py`, `asr/`, `extraction/`,
`manage.py`, `dev_seed.py`. The original `main.py`, `nlp_parser.py`, `audio_transcriber.py`, `database.py`
remain and are extended.

### Roles

| Role | Can |
|---|---|
| `admin` | Everything, incl. users, routing/SLA policy, audit trail, retained audio |
| `nurse` | Record/ingest, review & submit, tasks, patient search/create/link, appointments, read clinical data and medications |
| `clinician` | Nurse abilities + write clinical records and prescriptions, verify identity, approve follow-ups, play retained audio |
| `coordinator` | Tasks **for their own team only**, appointments, link patients |
| `pharmacist` | Their team's tasks, read/record verified prescriptions |
| `patient` | Their own portal only — every query is scoped to their profile |

---

## Quick start (Windows)

```powershell
cd D:\CareRouter-AI\backend
python -m venv venv ; .\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # then edit: JWT_SECRET etc. (never commit .env)

# first administrator (password is prompted, not a CLI argument)
python manage.py create-user admin.jane admin --full-name "Jane Admin"

uvicorn main:app --host 127.0.0.1 --port 8000 --reload     # API docs: http://127.0.0.1:8000/docs
```
```powershell
cd D:\CareRouter-AI\frontend
npm install
npm run dev                                                # http://localhost:5173
```
`run_all.bat` still starts both. Existing databases are upgraded automatically on startup
(`schema_migrations` ledger; your calls/tickets are preserved).

**Try it with fictional data (development only):**
```powershell
set DEV_SEED_PASSWORD=<12+ chars, mixed case, a digit>
python dev_seed.py     # creates dev.admin / dev.nurse / dev.clinician / dev.coordinator / dev.pharmacist / dev.patient
```
The script refuses to run when `APP_ENV=production` and stores no password in the repository.

### Configuration (`backend/.env.example` lists everything)

Key variables: `JWT_SECRET` (required in production), `CORS_ALLOWED_ORIGINS`, `HOSPITAL_TIMEZONE`,
`ASR_*`, `INDIC_ASR_ENABLED`, `AUDIO_RETENTION_HOURS`, `EXTRACTION_PROVIDER`, `EXTERNAL_LLM_ALLOWED`,
`APPOINTMENT_AUTO_CONFIRM`. Production must also sit behind HTTPS (TLS termination at your proxy).

---

## What works today vs. what needs your credentials or integration

| Item | State |
|---|---|
| Auth, roles, audit, rate limiting, migrations | ✅ working, tested |
| Whisper speech-to-text (background jobs) | ✅ working locally (live-tested end to end; accuracy not measured here) |
| IndicConformer | ⚙️ adapter written, **not run against the real weights** — needs gated HF access, packages, validation ([docs](docs/ASR_SETUP.md)) |
| Structured extraction (rules) | ✅ working, tested; English coverage is richest |
| LLM extraction | ⚙️ implemented and tested with a mocked transport only; needs `LLM_API_KEY`, `LLM_MODEL`, and `EXTERNAL_LLM_ALLOWED=true` after you have a data-processing agreement |
| Internal scheduler & patient portal | ✅ working, tested incl. a real concurrent-booking race |
| SMS / email reminders | ⚙️ queued in an outbox (`notifications`); **no delivery provider is configured**, rows stay `pending`, never marked sent. In-app messages work |
| Hospital EHR / scheduling / pharmacy integration | ❌ none exists; the internal models are the source of truth until an integration is built |
| Capturing the *caller's* side of a phone call | ❌ needs telephony integration; the browser mic hears only the nurse's side |

---

## Tests

```powershell
cd D:\CareRouter-AI
backend\venv\Scripts\pytest backend\tests -q
cd frontend ; npm run build ; npx oxlint
```

Last run: **235 passed, 8 failed** (backend). The 8 failures are the pre-existing
`test_stt_evaluation.py` accuracy tests: they need audio fixtures that must be generated on the machine
and currently point at another machine's absolute path — they fail identically on the untouched project.
Frontend: `tsc -b` clean and `vite build` succeeds; `oxlint` reports warnings only (no errors).

New suites cover: auth/RBAC/lockout/rate-limit/audit-chain tampering, audio validation, background jobs,
provider routing and fallback, extraction schema + grounding + LLM failure handling + emergency floor,
routing/policy, duplicate-task protection, patient matching and cross-patient isolation, prescription
integrity, slot availability, **concurrent booking** (12 threads, exactly one winner), timezones,
portal isolation, change requests, follow-up approval, and migration of a legacy database.

No test claims model accuracy. Nothing here is validated for clinical use.

---

## Privacy & safety

- Obtain consent before recording; the app enforces a consent confirmation and shows recording status.
- Audio is deleted right after transcription by default; retention is opt-in and audited.
- Transcripts and patient names are never written to logs; API errors never echo clinical text.
- Use **fictional** data for demos and tests. Do not send real patient data to an external LLM without
  authorisation and a data-processing agreement.
- The system flags emergencies for the hospital's approved escalation process; it does not dial 911/108.
