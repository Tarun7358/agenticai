@echo off
title AURA JARVIS — SATELLITE NODE (LAPTOP 2)
color 0b

echo ========================================================
echo       AURA JARVIS SATELLITE NODE (REMOTE PC)
echo ========================================================
echo.

cd /d "%~dp0"

if exist "backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=backend\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [*] Launching Satellite Client...
echo [*] Any commands spoken on this laptop will trigger HUD on Primary PC!
echo.
%PYTHON_EXE% jarvis\satellite_client.py
pause
