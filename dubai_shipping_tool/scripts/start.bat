@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
set "ROOT=%cd%"

echo ============================================
echo   Dubai Shipping Tool - Start
echo ============================================

echo.
echo Starting backend...
start "Dubai Shipping Backend" cmd /c "cd /d %ROOT%\backend && .venv\Scripts\activate.bat && python run.py"

echo Starting frontend...
start "Dubai Shipping Frontend" cmd /c "cd /d %ROOT%\frontend && npm run dev"

echo.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo.
echo Waiting for services to start...
timeout /t 5 /nobreak >nul

start http://localhost:5173

echo.
echo Services started. Close this window to keep them running.
pause
