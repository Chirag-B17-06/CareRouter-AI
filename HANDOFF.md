# CareRouter AI — Project Handoff Documentation

**Repository**: `https://github.com/Chirag-B17-06/CareRouter-AI`  
**Current Branch**: `main`  
**Last Updated**: October 11, 2026  
**Status**: Real Audio Microphone Recording & Upload + Multilingual Speech-to-Text (Kannada, Hindi, English) + Clinical Triage Task Dispatch Fully Operational

---

## 1. Executive Summary & Current State

CareRouter AI has transitioned from hardcoded demo scenarios to an end-to-end clinical voice-to-task triage dispatch platform. 

### What Has Been Implemented & Verified:
1. **Real Audio Microphone Recording**:
   - Built using browser `MediaRecorder` API with Opus/WebM encoding.
   - Live recording indicator, animated pulse ring, timer counter (`mm:ss`), pause/resume, playback preview, and discard options.
   - Clean hardware microphone release upon recording stop.
2. **Audio File Upload**:
   - Supports Drag-and-Drop and file selector for `.webm`, `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`.
   - Max file size validated up to 25 MB.
3. **Genuine Speech-to-Text (Faster-Whisper)**:
   - Powered by `faster-whisper-1.2.1` using Systran's `tiny` model cached locally on CPU (`int8` quantization).
   - Audio decoding handled natively in Python via PyAV and CTranslate2 without requiring system `ffmpeg.exe`.
   - Multilingual support for:
     - **Kannada (`kn`)**: Native Kannada Unicode script transcription (`Noto Sans Kannada`).
     - **Hindi (`hi`)**: Devanagari Unicode script transcription (`Noto Sans Devanagari`).
     - **English (`en`)**: Clinical English transcription (`Plus Jakarta Sans`).
     - **Auto-Detection (`auto`)**: Automatic language identification with confidence score.
4. **Editable Transcript Review (Step 2)**:
   - Medical staff review and edit the transcribed speech before dispatching tasks.
   - Preserves native script and permits correcting clinical terminology or patient names.
5. **Multi-Intent Extraction & Clinical Department Routing (Step 3)**:
   - Decomposes complex multi-sentence clinical calls into separate atomic department tasks:
     - **Rapid Response & Critical Nursing** (`STAT_EMERGENCY`)
     - **Nursing & Clinical Care** (`URGENT` / `ROUTINE`)
     - **Pharmacy & Therapeutics** (`URGENT` / `ROUTINE`)
     - **Dietary & Clinical Nutrition** (`ROUTINE`)
     - **Facilities & Environmental Services** (`ROUTINE` / `URGENT`)
     - **Administration & Discharge Coordination** (`ROUTINE` / `INQUIRY`)
   - **Clinical Negation Handling**: Contextual window inspection detects expressions like *"no chest pain"*, *"सीने में दर्द नहीं है"*, and *"ಎದೆ ನೋವು ಇಲ್ಲ"*, flagging them as rule-outs and preventing false STAT emergency alarms.
   - **Floor Spill vs Dietary Conflict Resolution**: Accurately differentiates Facilities spills (*"floor is wet / ನೆಲದ ಮೇಲೆ ನೀರು"*) from Dietary requests (*"glass of water / ಕುಡಿಯಲು ನೀರು"*).
   - **Greeting Filtering**: Intro phrases (*"Hi, this is nurse on 4th floor"*) do not trigger spurious tickets.
6. **Command Center Dashboard & Live Triage Board**:
   - Dynamic real-time statistics (Active Tasks, STAT Rapid Response, Pending Pickup, Ingested Calls).
   - STAT Emergency Alert Banner with pulsating glow and audio telemetry alert.
   - Grid and Kanban view modes.
   - Task advancement (`PENDING` -> `IN_PROGRESS` -> `DISPATCHED` -> `RESOLVED`).
   - Clinical notes logging with audit trails.
   - Multilingual filtering: Filter tasks by language (All, Kannada, Hindi, English).
   - Honest empty state with zero fake preloaded seed calls and a quick *"Record / Ingest First Call"* CTA.
7. **Hospital Analytics**:
   - Operational throughput and breakdown by urgency, department, and language intake distribution (`kn`, `hi`, `en`).

---

## 2. File Structure & Responsibilities

```
CareRouter-AI/
├── .gitignore                     # Excludes venv, .env, .db, node_modules, and backend/uploads/
├── README.md                      # Windows setup and operational guide
├── HANDOFF.md                     # Detailed architecture and handoff state (this file)
├── run_all.bat                    # One-click startup script for backend & frontend
├── start_backend.bat              # Script to launch FastAPI on port 8000
├── start_frontend.bat             # Script to launch Vite on port 5173
│
├── backend/
│   ├── audio_transcriber.py       # faster-whisper STT engine, audio validation (<=25MB)
│   ├── nlp_parser.py              # Multilingual intent extraction, negation, routing
│   ├── database.py                # SQLite schema (Call, Ticket, AuditLog models)
│   ├── schemas.py                 # Pydantic v2 validation models
│   ├── main.py                    # FastAPI REST endpoints (/api/audio, /api/calls, /api/tickets, /api/analytics)
│   ├── requirements.txt           # Python dependencies (fastapi, faster-whisper, uvicorn, etc.)
│   ├── tests/
│   │   └── test_api.py            # 14 passing pytest unit & integration tests
│   └── uploads/                   # Audio storage folder (gitignored)
│
└── frontend/
    ├── package.json
    ├── src/
    │   ├── types.ts               # TypeScript interfaces (Ticket, Call, AnalyticsData, etc.)
    │   ├── App.tsx                # Main view router (Board vs Record, Command Center counters)
    │   ├── index.css              # Design tokens, Google fonts (Noto Sans Kannada, Devanagari)
    │   ├── services/
    │   │   └── api.ts             # Axios client for audio upload, transcripts, tickets, analytics
    │   ├── utils/
    │   │   └── audio.ts           # Web Audio API procedural sound synthesizer (chimes, STAT alarm)
    │   └── components/
    │       ├── AudioRecorder.tsx      # MediaRecorder mic recording, upload, STT & dispatch
    │       ├── Navbar.tsx             # Sticky header with active tabs, sound toggle, STAT counter
    │       ├── EmergencyBanner.tsx    # STAT urgent alert banner with native script support
    │       ├── TicketBoard.tsx        # Department & Language filtered Kanban/Grid board
    │       ├── TicketCard.tsx         # Individual ticket card with script badge & quote
    │       ├── TicketDetailModal.tsx  # Detailed audit view, translation, staff notes
    │       └── AnalyticsModal.tsx     # Department, urgency, and language distribution metrics
```

---

## 3. Verification & Test Results

### Backend Pytest (All 14 Passed in 0.79s):
```
backend/tests/test_api.py::test_health_check PASSED                      [  7%]
backend/tests/test_api.py::test_empty_state_initial PASSED               [ 14%]
backend/tests/test_api.py::test_audio_validation_empty_file PASSED       [ 21%]
backend/tests/test_api.py::test_audio_validation_invalid_format PASSED   [ 28%]
backend/tests/test_api.py::test_audio_validation_oversized PASSED        [ 35%]
backend/tests/test_api.py::test_process_english_multi_intent_and_stat PASSED [ 42%]
backend/tests/test_api.py::test_process_hindi_multi_intent_and_devanagari_script PASSED [ 50%]
backend/tests/test_api.py::test_process_kannada_multi_intent_and_kannada_script PASSED [ 57%]
backend/tests/test_api.py::test_emergency_negation_handling_english PASSED [ 64%]
backend/tests/test_api.py::test_emergency_negation_handling_hindi PASSED [ 71%]
backend/tests/test_api.py::test_emergency_negation_handling_kannada PASSED [ 78%]
backend/tests/test_api.py::test_duplicate_submission_guard PASSED        [ 85%]
backend/tests/test_api.py::test_ticket_status_update_and_notes PASSED    [ 92%]
backend/tests/test_api.py::test_delete_call_and_tickets PASSED           [100%]
============================= 14 passed in 0.79s ==============================
```

### Frontend TypeScript & Bundler:
```
> frontend@0.0.0 build
> tsc -b && vite build
✓ 1916 modules transformed.
✓ built in 658ms
```
Zero TypeScript errors, zero unresolved imports.

---

## 4. How to Run on Windows

### Option A: 1-Click Launch
Double-click `run_all.bat` in the repository root. This will:
1. Start the FastAPI backend on `http://127.0.0.1:8000`.
2. Start the Vite React development server on `http://127.0.0.1:5173`.
3. Open your default web browser to the dashboard.

### Option B: Manual Command Line
**Terminal 1 (Backend):**
```powershell
cd D:\CareRouter-AI\backend
.\venv\Scripts\activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 (Frontend):**
```powershell
cd D:\CareRouter-AI\frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## 5. Security & Safety Commitments
- `.env`, `.db`, `node_modules`, `backend/venv`, and `backend/uploads/` are excluded by `.gitignore`.
- No sensitive keys or patient voice recordings are pushed to GitHub.
- Clean database startup with no fake pre-seeded data in runtime.
