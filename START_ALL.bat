@echo off
chcp 65001 > nul
echo ========================================================
echo   Launching MATGAR LMS Services...
echo ========================================================
echo.

echo [1/2] Launching LMS Core Backend API (:8000)...
start "Matgar LMS - Core Backend (:8000)" cmd /k call "%~dp0START_API.bat"
timeout /t 2 > nul

timeout /t 2 > nul

echo [2/2] Launching LMS Web Frontend (:5173)...
start "Matgar LMS - Web Frontend (:5173)" cmd /k call "%~dp0START_FRONTEND.bat"

echo.
echo ========================================================
echo   All services are launched!
echo   - Web App:      http://localhost:5173
echo   - Core API:     http://localhost:8000 (Docs: /docs)
echo ========================================================
echo.
