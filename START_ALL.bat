@echo off
chcp 65001 > nul
echo ========================================================
echo   Launching MATGAR LMS Full Stack Services...
echo ========================================================
echo.

echo [1/3] Launching LMS Core Backend API (:8000)...
start "Matgar LMS - Core Backend (:8000)" cmd /k call "%~dp0START_API.bat"
timeout /t 2 > nul

echo [2/3] Launching LMS AI Service (:8001)...
start "Matgar LMS - AI Service (:8001)" cmd /k call "%~dp0START_AI_SERVICE.bat"
timeout /t 2 > nul

echo [3/3] Launching LMS Web Frontend (:5173)...
start "Matgar LMS - Web Frontend (:5173)" cmd /k call "%~dp0START_FRONTEND.bat"

echo.
echo ========================================================
echo   All 3 services are launched!
echo   - Web App:      http://localhost:5173
echo   - Core API:     http://localhost:8000 (Docs: /docs)
echo   - AI Service:   http://localhost:8001 (Docs: /docs)
echo ========================================================
echo.
