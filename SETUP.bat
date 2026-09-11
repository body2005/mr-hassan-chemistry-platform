@echo off
chcp 65001 > nul
echo ========================================================
echo   MATGAR LMS - Unified Project Dependencies Setup
echo ========================================================
echo.

echo [1/3] Installing Web Frontend Dependencies (npm)...
cd /d "%~dp0apps\web"
call npm install
echo [OK] Web Frontend dependencies installed.
echo.

echo [2/3] Setting up LMS Backend API Virtualenv...
cd /d "%~dp0apps\api"
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
echo [OK] LMS Backend API environment ready.
echo.

echo [3/3] Setting up AI Service Virtualenv...
cd /d "%~dp0apps\ai-service"
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
echo [OK] AI Service environment ready.
echo.

echo ========================================================
echo   Setup Complete! You can now double click START_ALL.bat
echo ========================================================
pause
