@echo off
echo ========================================================
echo   Starting CareRouter AI - FastAPI Backend (Port 8000)
echo ========================================================
cd /d "%~dp0\backend"

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3.11 -m venv venv
    call venv\Scripts\pip install -r requirements.txt
)

echo Starting uvicorn server...
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
