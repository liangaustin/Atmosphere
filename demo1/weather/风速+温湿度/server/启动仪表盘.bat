@echo off
title Wind Dashboard
cd /d "%~dp0"
echo ============================================
echo   Wind Dashboard
echo   1. wind_server.py  -^> port 8001 (serial)
echo   2. node server.js  -^> port 3000 (web)
echo   Browser: http://localhost:3000
echo   Close this window to stop dashboard
echo ============================================
start "wind-forward-8001" python wind_server.py
timeout /t 2 /nobreak >nul
node server.js
pause
