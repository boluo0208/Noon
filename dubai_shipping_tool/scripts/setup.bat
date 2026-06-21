@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo ============================================
echo   Dubai Shipping Tool - Setup
echo ============================================

echo.
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.9+
    pause
    exit /b 1
)
python --version

echo.
echo [2/4] Setting up backend virtual environment...
cd backend
if not exist ".venv" (
    python -m venv .venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies.
    pause
    exit /b 1
)
python -m playwright install msedge
cd ..

echo.
echo [3/4] Checking Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)
node --version

echo.
echo [4/5] Installing frontend dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Node.js dependencies.
    pause
    exit /b 1
)
cd ..

echo.
echo [5/5] Checking .env file...
if not exist ".env" (
    copy .env.example .env
    echo .env file created from .env.example.
) else (
    echo .env file already exists.
)

echo.
echo ============================================
echo   Setup complete!
echo ============================================
pause
