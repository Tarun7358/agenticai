@echo off
title AURA Backend
echo.
echo  ==============================
echo    AURA Personal AI - Backend
echo  ==============================
echo.

cd /d "%~dp0backend"

:: Create venv if not exists
if not exist "venv" (
    echo [*] Creating Python virtual environment...
    python -m venv venv
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install dependencies
echo [*] Checking dependencies...
pip install -r requirements.txt -q

:: Copy env if not exists
if not exist ".env" (
    echo [*] Creating .env from template...
    copy .env.example .env
    echo [!] Please edit backend\.env with your settings!
    pause
)

:: Create data directory
if not exist "data" mkdir data

echo.
echo [*] Starting AURA backend on http://127.0.0.1:8000
echo [*] API docs: http://127.0.0.1:8000/docs
echo.
set PYTHONIOENCODING=utf-8
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
