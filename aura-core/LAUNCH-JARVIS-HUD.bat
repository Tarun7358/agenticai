@echo off
title AURA JARVIS HUD - Iron Man Mode
cd /d "%~dp0"

echo.
echo  ======================================================
echo    AURA - JARVIS HOLOGRAPHIC HUD
echo    Iron Man Desktop Personal Assistant
echo  ======================================================
echo.
echo [*] Wake Word: "Hey Aura" or "Jarvis"
echo [*] Hotkeys:   Ctrl+Shift+A  or  Alt+Space
echo [*] Telemetry: RTX 2050 GPU, 8GB RAM, System Watchers
echo.

:: Ensure UTF-8 console
set PYTHONIOENCODING=utf-8

:: Check if backend is running, if not start it silently in background
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/status' -TimeoutSec 2 -UseBasicParsing; Write-Host '[*] Backend already running.' } catch { Start-Process cmd -ArgumentList '/c start-backend.bat' -WindowStyle Hidden; Write-Host '[*] Starting background AURA services...' }"

timeout /t 2 /nobreak >nul

echo [*] Launching Jarvis Hologram HUD...
echo.
"%~dp0backend\venv\Scripts\python.exe" "%~dp0jarvis\jarvis_app.py"

pause
