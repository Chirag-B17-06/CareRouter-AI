# CareRouter AI 🏥🎙️

> **Multilingual Clinical Voice-to-Task Dispatch System**  
> Decomposes multi-request hospital phone calls and staff voice notes into prioritized, department-specific clinical tickets with automated STAT emergency detection.

---

## 🌟 Key Features

1. **Real Microphone Recording & File Intake**:
   - Record clinical calls directly using your microphone with live elapsed timer, pause, resume, and preview.
   - Upload audio files in WebM, WAV, MP3, M4A, OGG, or FLAC (up to 25 MB).
   - Zero pre-recorded fake audio or mock transcripts.
2. **Multilingual Speech-to-Text (STT)**:
   - Genuine speech recognition powered by `faster-whisper` running locally on CPU.
   - Native script transcription for:
     - **ಕನ್ನಡ (Kannada)** (`Noto Sans Kannada`)
     - **हिन्दी (Hindi)** (`Noto Sans Devanagari`)
     - **English** (`Plus Jakarta Sans`)
     - **Auto-Detection** with confidence telemetry.
3. **Multi-Intent Clinical Decomposition**:
   - Deconstructs single phone calls containing multiple requests into separate atomic tasks across 6 hospital departments:
     - *Rapid Response & Critical Nursing* (STAT Emergency)
     - *Nursing & Clinical Care* (Urgent / Routine)
     - *Pharmacy & Therapeutics* (Urgent / Routine)
     - *Dietary & Clinical Nutrition* (Routine)
     - *Facilities & Environmental Services* (Routine / Urgent)
     - *Administration & Discharge Coordination* (Routine / Inquiry)
4. **Clinical Negation & Rule-Out Handling**:
   - Recognizes negated symptom statements (e.g., *"no chest pain"*, *"सीने में दर्द नहीं है"*, *"ಎದೆ ನೋವು ಇಲ್ಲ"*), assigning clinical rule-out flags rather than false STAT emergency alarms.
5. **Hospital Command Center & Live Triage Board**:
   - STAT Emergency Alert Banner with pulsating audio-visual cues.
   - Department filter tabs and language-based filtering (Kannada, Hindi, English).
   - Kanban board and Grid view modes.
   - Task advancement (`PENDING` ➔ `IN_PROGRESS` ➔ `DISPATCHED` ➔ `RESOLVED`).
   - Clinical triage notes and immutable audit log trail.
   - Real-time operational throughput analytics.

---

## 🛠️ Technology Stack

- **Frontend**: React 18, TypeScript, Tailwind CSS, Lucide Icons, Vite
- **Audio Synthesizer**: Web Audio API (procedural alert chime & emergency tone)
- **Backend**: Python 3.11, FastAPI, Uvicorn, Pydantic v2
- **STT Engine**: `faster-whisper-1.2.1` (Systran `tiny` model cached locally, PyAV / CTranslate2 on CPU)
- **Database**: SQLite (SQLAlchemy ORM)
- **Test Framework**: Pytest

---

## 🚀 Quick Start on Windows

### Method 1: One-Click Startup (Recommended)
Double-click `run_all.bat` in the root folder.
This script automatically:
1. Starts the FastAPI backend at `http://127.0.0.1:8000`.
2. Starts the Vite React frontend at `http://127.0.0.1:5173`.
3. Opens your browser to the CareRouter AI dashboard.

---

### Method 2: Manual Terminal Startup

#### 1. Backend Setup:
```powershell
# Open terminal in backend directory
cd D:\CareRouter-AI\backend

# Activate virtual environment
.\venv\Scripts\activate

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Start backend server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation will be live at: `http://127.0.0.1:8000/docs`

#### 2. Frontend Setup:
```powershell
# Open terminal in frontend directory
cd D:\CareRouter-AI\frontend

# Install node dependencies (if not already installed)
npm install

# Start development server
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🧪 Running Tests

### Backend Unit & Integration Tests (14 Tests):
```powershell
cd D:\CareRouter-AI
backend\venv\Scripts\pytest backend\tests -v
```
All 14 tests validate:
- Initial clean empty state
- Audio validation (empty file, invalid extension, oversized file)
- Multi-intent decomposition in English, Hindi, and Kannada
- Negation handling in all 3 languages
- Duplicate submission prevention
- Status progression & audit trail
- Call cascade deletion

### Frontend Production Build Test:
```powershell
cd D:\CareRouter-AI\frontend
npm run build
```

---

## 🔒 Privacy & Safety Notice
- **Consent**: Obtain patient consent before recording hospital conversations.
- **Decision Support**: CareRouter AI is a clinical decision-support triage prototype; it does not automatically dispatch external 911/108 units.
- **Security**: Audio uploads and database files are excluded from Git version control. No API keys or credentials are required or stored.