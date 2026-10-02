@echo off
title AURA Frontend
echo.
echo  ===============================
echo    AURA Personal AI - Frontend
echo  ===============================
echo.

cd /d "%~dp0frontend"
echo [*] Starting AURA dashboard at http://localhost:5173
echo.
cmd /c "npm run dev"
