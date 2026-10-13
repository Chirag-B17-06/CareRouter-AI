# CareRouter AI — Handoff

**Repository:** `https://github.com/Chirag-B17-06/CareRouter-AI` · **Branch:** `main`
**State:** v3 upgrade implemented in the working tree and **not committed** (review, then commit).

See [README.md](README.md) for features/setup and [docs/ASR_SETUP.md](docs/ASR_SETUP.md) for speech models.

## 1. What changed in this upgrade

Everything is additive to the original app; no working feature was removed.

**Backend (`backend/`)**
| File | Purpose |
|---|---|
| `config.py` | Env-driven settings; production refuses to start without `JWT_SECRET` |
| `auth.py` | scrypt passwords, JWT sessions (revocable), role→permission map, lockout, user admin routes |
| `audit.py` | Hash-chained audit events; PHI-stripped `detail` |
| `ratelimit.py` | Per-process sliding-window limiter (use a gateway when scaling out) |
| `models_care.py` | users, patients, clinical records, medications, clinicians/slots/appointments, follow-ups, patient requests, notifications, routing rules, app settings, transcription jobs, audit events |
| `migrations.py` | Versioned migrations (`schema_migrations`); run from `init_db()` |
| `asr/` | Provider interface, audio normalisation (16 kHz mono WAV), Whisper + IndicConformer adapters, routing, background jobs |
| `extraction/` | Strict schema + grounding, rule extractor (reuses `nlp_parser`), optional LLM extractor, emergency safety floor |
| `routing.py` | Rules, fallback queue, emergency bypass, SLA policy, admin API |
| `patients.py`, `patient_matching.py` | Profiles, fuzzy matching, human-confirmed linking, clinical records, immutable prescriptions |
| `scheduling.py` | Slots, atomic booking, staff API, patient-portal API, outbox |
| `tasks_service.py` | One place that creates tasks (SLA, routing, dedupe, audit) |
| `manage.py`, `dev_seed.py` | Operations CLI; fictional dev data |

Modified: `main.py` (all routes now require a permission; actor names come from the session; new job/ASR/audit
endpoints; intake rewritten around extraction + matching + `create_ticket`), `database.py`, `schemas.py`,
`nlp_parser.py`, `requirements.txt`, `.env.example`.

**Frontend (`frontend/src/`)** — `LoginScreen`, role-aware `Navbar`, `PatientsView`, `SchedulingView`,
`AdminView`, `PatientPortal`, `ConversationReview`, `AuthAudio`, `ui.tsx`, `services/session.ts`,
`services/careApi.ts`, `utils/useLiveTranscription.ts`. `api.ts` now sends the bearer token on every
call and uploads audio through background jobs. `AudioRecorder` gained the consent gate, dynamic
languages, live transcript and review panel; `TicketBoard/Card/DetailModal` understand the new statuses
and any admin-created team.

## 2. Behaviour changes you should know about

1. **Every API route except `/api/health` and `/api/auth/login` requires a signed-in user.** Existing API
   consumers must authenticate.
2. **Actor names are server-derived.** `acknowledged_by`, `resolved_by`, `author`, `assigner`,
   `reviewer_name`, `escalated_by` in request bodies are ignored (they were spoofable). Seven legacy test
   assertions were updated accordingly.
3. **Audio needs consent and is deleted after transcription** (default). `/api/audio/transcribe` still
   exists (short clips, synchronous) but also requires `recording_consent=true`; prefer `/api/audio/jobs`.
4. **Patient linking is never automatic.** Name-only matches are `needs_confirmation`.
5. CORS is no longer `*`; set `CORS_ALLOWED_ORIGINS`.

## 3. Pre-existing defects found and fixed

- **Clinical sentences silently dropped.** The "greeting filter" discarded any sentence lacking a known
  keyword, so *"Reports a possible right forearm fracture"* vanished whenever another sentence in the same
  call matched (e.g. billing). It now drops only text that positively looks like a greeting/introduction/bare
  patient identification; unknown sentences become reviewable tasks. Regression tests added.
- `Dr.`/`Mr.` abbreviations were treated as sentence ends (one call produced a spurious task).
- Resolved/closed state: overdue logic now treats `CLOSED` as terminal.

## 4. Known limitations / next steps

- **IndicConformer has not been run against real weights in this repo.** Validate and measure WER on your own audio first.
- **No telephony integration:** the browser mic hears only the nurse.
- **No SMS/email provider; no EHR/scheduling/pharmacy integration** (interfaces/outbox only).
- Live transcript is segment-based (~15 s) — near-live, with word splits possible at boundaries.
- Rule-based extraction vocabulary is English-centric; Hindi/Kannada rely on the rule engine's emergency terms and
  human review (or the LLM provider once authorised).
- Rate limiting is per process; background workers are in-process threads (see ASR doc for scaling out).
- No configurable *transcript* retention/deletion yet (audio retention is implemented). Add per your legal policy.
- Access tokens live in `sessionStorage`; consider httpOnly-cookie sessions + CSRF if your threat model requires it.
- The 8 `test_stt_evaluation.py` tests need locally generated audio fixtures (they hard-code another machine's path).
- No browser E2E test suite; the UI was verified manually (login, record→review→link, portal booking, admin, audit).
- Not verified for production or clinical use; a security review and clinical-safety sign-off are required.
