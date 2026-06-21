@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo ============================================
echo   Dubai Shipping Tool - Setup
echo ============================================
echo.

:: ========================================
:: Step 1: Auto-install Python if missing
:: ========================================
echo [1/6] 检查 Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python 未安装，正在通过 winget 自动安装...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
    if %errorlevel% neq 0 (
        echo.
        echo ERROR: 自动安装 Python 失败。
        echo 请手动下载安装: https://www.python.org/downloads/
        echo 安装时务必勾选 "Add Python to PATH"
        pause
        exit /b 1
    )
    :: Refresh PATH for current session
    for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH ^| findstr PATH') do set "PATH=%%b;%PATH%"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
    echo Python 安装完成，请重新打开此脚本继续。
    echo.
    pause
    exit /b 0
)
python --version
echo.

:: ========================================
:: Step 2: Python virtual environment
:: ========================================
echo [2/6] 配置 Python 虚拟环境...
cd backend
if not exist ".venv" (
    python -m venv .venv
    echo 虚拟环境已创建.
) else (
    echo 虚拟环境已存在.
)
call .venv\Scripts\activate.bat

echo [3/6] 安装 Python 依赖（使用清华镜像源，国内更快）...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo ERROR: Python 依赖安装失败.
    pause
    exit /b 1
)

echo [4/6] 安装 Playwright 浏览器...
python -m playwright install msedge
cd ..
echo.

:: ========================================
:: Step 3: Auto-install Node.js if missing
:: ========================================
echo [5/6] 检查 Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Node.js 未安装，正在通过 winget 自动安装...
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements --silent
    if %errorlevel% neq 0 (
        echo.
        echo ERROR: 自动安装 Node.js 失败。
        echo 请手动下载安装: https://nodejs.org
        echo.
        pause
        exit /b 1
    )
    :: Refresh PATH
    for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH ^| findstr PATH') do set "PATH=%%b;%PATH%"
    set "PATH=%ProgramFiles%\nodejs;%PATH%"
    echo Node.js 安装完成，请重新打开此脚本继续。
    echo.
    pause
    exit /b 0
)
node --version
echo.

:: ========================================
:: Step 4: Frontend dependencies
:: ========================================
echo [6/6] 安装前端依赖（使用淘宝镜像源，国内更快）...
cd frontend
call npm config set registry https://registry.npmmirror.com
call npm install
if %errorlevel% neq 0 (
    echo ERROR: 前端依赖安装失败.
    pause
    exit /b 1
)
cd ..
echo.

:: ========================================
:: Create .env if missing
:: ========================================
if not exist ".env" (
    copy .env.example .env >nul
    echo .env 文件已创建.
) else (
    echo .env 文件已存在，跳过.
)

echo ============================================
echo   安装完成！双击 start.bat 启动系统
echo ============================================
pause
