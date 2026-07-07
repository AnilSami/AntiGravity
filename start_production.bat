@echo off
echo ===================================================
echo   ClipMind - YouTube AI Clip Extractor (Production)
echo ===================================================
echo.

cd /d "%~dp0"

:: Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    pause
    exit /b
)

cd backend

:: Ensure venv exists
if not exist "venv" (
    echo [ERROR] Virtual environment not found. Please run start_all.bat first to set up the system.
    pause
    exit /b
)

:: Activate Virtual Environment
call venv\Scripts\activate.bat

:: Verify .env configuration
if not exist ".env" (
    echo [WARNING] .env file is missing.
    if exist ".env.example" (
        copy .env.example .env
        echo [INFO] Copied .env.example to .env
    ) else (
        echo [ERROR] Environment configuration file (.env) is missing.
        pause
        exit /b
    )
)

echo.
echo ==========================================================
echo   [INFO] Starting ClipMind in PRODUCTION mode.
echo   [INFO] Listening on: http://localhost:8000
echo   [INFO] Hot-reloader is DISABLED for stability and performance.
echo ==========================================================
echo.

:: Run uvicorn server in production (no --reload, using single worker for Windows asyncio loop stability)
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

pause
