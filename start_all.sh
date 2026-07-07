#!/bin/bash
# ClipMind Local Development Startup Script for Linux and macOS

echo "==================================================="
echo "  ClipMind - YouTube AI Clip Extractor Bootstrapper"
echo "==================================================="
echo ""

# Navigate to script directory
cd "$(dirname "$0")"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in your PATH."
    exit 1
fi

cd backend

# Create Virtual Environment if it does not exist
if [ ! -d "venv" ]; then
    echo "[INFO] Creating Python virtual environment (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
fi

# Activate Virtual Environment
echo "[INFO] Activating virtual environment..."
source venv/bin/activate

# Install Requirements
echo "[INFO] Installing / updating dependencies..."
python3 -m pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Dependency installation failed."
    exit 1
fi

# Verify dependencies
python3 -c "import fastapi, yt_dlp, youtube_transcript_api, google.generativeai; print('[INFO] Backend dependencies verified successfully!')"
if [ $? -ne 0 ]; then
    echo "[ERROR] Dependency verification failed."
    exit 1
fi

echo ""
echo "=========================================================="
echo "  [SUCCESS] Backend server is starting on http://localhost:8000"
echo "  [ACTION] Open frontend/index.html in your browser!"
echo "=========================================================="
echo ""

python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
