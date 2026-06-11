@echo off
echo ===================================================
echo   ClipMind - YouTube AI Clip Extractor Bootstrapper
echo ===================================================
echo.

cd /d "%~dp0"

:: Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b
)

:: Move into backend folder
cd backend

:: Create Virtual Environment if it does not exist
if not exist "venv" (
    echo [INFO] Creating Python virtual environment ^(venv^)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
)

:: Activate Virtual Environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

:: Install Requirements
echo [INFO] Installing / updating dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b
)

:: Verify installation
python -c "import fastapi, yt_dlp, youtube_transcript_api, google.generativeai; print('[INFO] Backend dependencies verified successfully!')"
if %errorlevel% neq 0 (
    echo [ERROR] Dependency verification failed.
    pause
    exit /b
)

echo.
echo ==========================================================
echo   [SUCCESS] Backend server is starting on http://localhost:8000
echo   [ACTION] Double-click frontend/index.html to open ClipMind!
echo ==========================================================
echo.
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
