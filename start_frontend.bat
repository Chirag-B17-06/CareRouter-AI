@echo off
echo ========================================================
echo   Starting CareRouter AI - React Frontend (Port 5173)
echo ========================================================
cd /d "%~dp0\frontend"

if not exist "node_modules" (
    echo Installing npm dependencies...
    call npm install
)

echo Starting Vite development server...
call npm run dev
pause
