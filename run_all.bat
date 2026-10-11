@echo off
echo ========================================================
echo   Launching CareRouter AI Full Stack Application
echo ========================================================
echo Starting Backend in a separate window...
start "CareRouter Backend" cmd /k "%~dp0start_backend.bat"

timeout /t 3 /nobreak >nul

echo Starting Frontend in a separate window...
start "CareRouter Frontend" cmd /k "%~dp0start_frontend.bat"

timeout /t 4 /nobreak >nul

echo Opening browser at http://127.0.0.1:5173 ...
start http://127.0.0.1:5173

echo ========================================================
echo   CareRouter AI is running!
echo   Frontend: http://127.0.0.1:5173
echo   Backend API: http://127.0.0.1:8000
echo   API Docs: http://127.0.0.1:8000/docs
echo ========================================================
pause
