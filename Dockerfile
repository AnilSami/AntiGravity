# Production-Ready Dockerfile for ClipMind
FROM python:3.11-slim

# Install system dependencies (FFmpeg is required for video extraction and rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend requirements first to leverage Docker layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application source code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Set working directory to backend so config file and main app are resolved correctly
WORKDIR /app/backend

# Create volume directory for persistent outputs (cache, database, and clip exports)
RUN mkdir -p /app/backend/output

EXPOSE 8000

# Set environment variables defaults
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APP_ENV=production

# Startup command running Uvicorn server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
