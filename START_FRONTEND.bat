@echo off
chcp 65001 > nul
cd /d "%~dp0apps\web"
echo ========================================================
echo   Starting MATGAR LMS - Web Frontend (React + Vite)
echo   URL: http://localhost:5173
echo ========================================================
echo.
npm run dev
