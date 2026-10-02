@echo off
title AURA - Personal AI Assistant
echo.
echo  ====================================
echo    AURA - Your Personal AI
echo    Starting all services...
echo  ====================================
echo.

:: Start backend in new window
start "AURA Backend" cmd /k "cd /d %~dp0 && start-backend.bat"

:: Wait 3 seconds
timeout /t 3 /nobreak >nul

:: Start frontend in new window
start "AURA Frontend" cmd /k "cd /d %~dp0 && start-frontend.bat"

:: Wait 4 seconds then open browser
timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo [✓] AURA is starting up!
echo     Backend:   http://127.0.0.1:8000
echo     Dashboard: http://localhost:5173
echo.
echo     Close this window when you're done.
pause
