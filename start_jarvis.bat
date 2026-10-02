@echo off
title JARVIS Voice HUD
cd /d "%~dp0\aura-core\jarvis"
set PYTHONIOENCODING=utf-8
"..\backend\venv\Scripts\python.exe" jarvis_app.py
pause
