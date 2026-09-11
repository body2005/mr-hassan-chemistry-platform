@echo off
chcp 65001 > nul
cd /d "%~dp0apps\api"
echo ========================================================
echo   Starting MATGAR LMS - Core API Backend (FastAPI)
echo   URL: http://localhost:8000
echo   Docs: http://localhost:8000/docs
echo ========================================================
echo.
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) else (
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
)
