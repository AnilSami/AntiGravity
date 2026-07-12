# Production-Ready Dockerfile for ClipMind
# Uses $PORT env var so Railway can bind dynamically (Railway injects PORT at runtime)
FROM python:3.11-slim

# Install system dependencies
# - ffmpeg: required for all video extraction and rendering
# - libgl1-mesa-glx + libglib2.0-0: OpenCV runtime dependencies
# - libsm6, libxext6, libxrender-dev: OpenCV display libraries
# - libgomp1: OpenMP for parallel processing (numpy/cv2)
RUN apt-get update || (sleep 5 && apt-get update)
RUN apt-get install -y --no-install-recommends --fix-missing \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    || (sleep 5 && apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl) \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first — leverages Docker layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application source code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY assets/ /app/assets/

# Create all required output subdirectories
RUN mkdir -p /app/backend/output/clips \
             /app/backend/output/cache \
             /app/backend/output/cache/transcripts \
             /app/backend/output/cache/checkpoints \
             /app/backend/output/debug \
             /app/backend/output/shorts \
             /app/backend/output/temp_subs

WORKDIR /app/backend

# Mount point for persistent storage (Railway volumes)
VOLUME ["/app/backend/output"]

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    APP_ENV=production

# Use $PORT injected by Railway at runtime (default 8000 for local docker run)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
