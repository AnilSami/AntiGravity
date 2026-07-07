# Quick Start Guide — ClipMind v1.0

Get ClipMind up and running in under 2 minutes.

---

## 🚀 Running locally (Windows)

If you are on Windows, you can use the pre-configured startup script in the workspace root:

1. Double-click or run the batch script in the repository root:
   ```cmd
   start_all.bat
   ```
   This will:
   - Verify Python is installed and create a virtual environment under `backend/venv` if it doesn't exist.
   - Install backend requirements.
   - Start the FastAPI/Uvicorn server at `http://127.0.0.1:8000`.
   - Open your default browser to launch the web dashboard.

---

## 🐳 Running with Docker

Alternatively, run the containerized setup in a single command:

1. Start the Docker containers:
   ```bash
   docker-compose up --build -d
   ```
2. Open your browser and navigate to:
   ```text
   http://localhost:8000
   ```
3. Monitor logs to see the startup health checks:
   ```bash
   docker-compose logs -f
   ```

---

## 🎬 How to Extract Your First Highlight Clip

1. **Submit Video**: Copy and paste any YouTube video URL into the main URL input bar.
2. **Configure Target Clips**:
   - Open Advanced Settings.
   - Select **Target Number of Clips** (e.g. `1 Clip (Credit Saver) 💎` to minimize API token cost, or `3 Clips`).
   - Select your preferred subtitle font and styling preset.
3. **Execute**: Click **Analyze & Clip Video**.
4. **SSE Progress**: Watch the real-time visual progress stream mapping transcription, analytics, and video rendering.
5. **View Clips**: Once finished, download your vertical 9:16 Shorts with stylized subtitles directly from the UI!
