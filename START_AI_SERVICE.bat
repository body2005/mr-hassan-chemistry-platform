@echo off
chcp 65001 > nul
cd /d "%~dp0apps\ai-service"
echo ========================================================
echo   Starting MATGAR LMS - AI & Predictive Intelligence Service
echo   URL: http://localhost:8001
echo   Docs: http://localhost:8001/docs
echo ========================================================
echo.
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
) else (
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
)
