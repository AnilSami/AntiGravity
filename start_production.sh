#!/bin/bash
# ClipMind Production Startup Script using Docker Compose

echo "==================================================="
echo "  ClipMind - Production Server Bootstrapper"
echo "==================================================="
echo ""

# Navigate to script directory
cd "$(dirname "$0")"

# Check for Docker and Docker Compose
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed or the daemon is not running."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "[ERROR] Docker Compose is not installed."
    exit 1
fi

# Ensure .env exists in backend directory
if [ ! -f "backend/.env" ]; then
    echo "[WARNING] backend/.env file is missing."
    if [ -f "backend/.env.example" ]; then
        echo "[INFO] Copying .env.example to backend/.env..."
        cp backend/.env.example backend/.env
    elif [ -f ".env.example" ]; then
        echo "[INFO] Copying .env.example to backend/.env..."
        cp .env.example backend/.env
    else
        echo "[ERROR] No environment configuration file found. Please create backend/.env."
        exit 1
    fi
    echo "[IMPORTANT] Please open backend/.env and fill in production secrets before running!"
fi

echo "[INFO] Starting ClipMind production container in detached mode..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d --build
else
    docker compose up -d --build
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================================="
    echo "  [SUCCESS] ClipMind is running in the background!"
    echo "  [URL] Access the REST API at http://localhost:8000"
    echo "  [LOGS] View logs with: docker logs -f clipmind-container"
    echo "=========================================================="
else
    echo "[ERROR] Failed to start Docker container."
    exit 1
fi
