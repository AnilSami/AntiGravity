import os
import uuid
import json
import logging
import asyncio
import time
import shutil
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from job_manager import jobs, run_pipeline, JobStatus
from clipper import check_ffmpeg

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

# Load environment variables from .env file
load_dotenv()


async def cleanup_old_jobs():
    """Background task to delete old jobs and clip folders (older than 1 hour) to save disk space."""
    while True:
        await asyncio.sleep(600)  # Check every 10 minutes
        logger.info("Running job cleanup check...")
        now = time.time()
        
        # 1. Purge old jobs from in-memory dictionary
        for job_id, job in list(jobs.items()):
            is_old = False
            if job.created_at > 0:
                if now - job.created_at > 3600:
                    is_old = True
            else:
                is_old = job.status in ["completed", "failed"]
            
            if is_old:
                jobs.pop(job_id, None)
                logger.info(f"Purged old job {job_id} from memory.")

        # 2. Clean up old or orphaned clip folders on disk
        output_dir = "output"
        if os.path.exists(output_dir):
            try:
                for folder_name in os.listdir(output_dir):
                    folder_path = os.path.join(output_dir, folder_name)
                    if os.path.isdir(folder_path):
                        mtime = os.path.getmtime(folder_path)
                        # Clean if orphaned (not in memory map) or modified > 1 hour ago
                        if folder_name not in jobs or (now - mtime > 3600):
                            try:
                                shutil.rmtree(folder_path)
                                logger.info(f"Cleaned up expired/orphaned folder: {folder_path}")
                            except Exception as e:
                                logger.error(f"Failed to delete expired folder {folder_path}: {e}")
            except Exception as e:
                logger.error(f"Error listing output directory during cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and graceful shutdown."""
    # --- Startup ---
    os.makedirs("output", exist_ok=True)
    cleanup_task = asyncio.create_task(cleanup_old_jobs())
    logger.info("Server started. Output directory ready.")
    yield
    # --- Shutdown ---
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Server shutting down cleanly.")


# Create the FastAPI app — lifespan must be defined before this line
app = FastAPI(title="YouTube Smart Clip Extractor API", lifespan=lifespan)

# Enable CORS for frontend compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    url: str
    gemini_api_key: Optional[str] = None
    num_clips: int = Field(default=5, ge=1, le=10)


@app.post("/api/analyze")
async def analyze_video(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    # Validate ffmpeg exists before allowing submission
    if not check_ffmpeg():
        raise HTTPException(
            status_code=500,
            detail="ffmpeg is not installed or not in PATH on this server. Video clipping is disabled."
        )

    # Determine API key (request > .env fallback)
    api_key = request.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="API Key is missing. Please provide a Gemini or OpenAI key in the input field or set GEMINI_API_KEY/OPENAI_API_KEY in .env."
        )

    job_id = str(uuid.uuid4())
    logger.info(f"Queuing job {job_id} for URL: {request.url}")

    # Initialize job status
    jobs[job_id] = JobStatus(
        id=job_id,
        status="pending",
        progress=0,
        message="Initializing job...",
        created_at=time.time()
    )

    if request.num_clips < 1 or request.num_clips > 10:
        raise HTTPException(
            status_code=400,
            detail="Number of clips must be between 1 and 10."
        )

    # Launch processing in background
    background_tasks.add_task(run_pipeline, job_id, request.url, api_key, request.num_clips)

    return {"job_id": job_id}


@app.get("/api/progress/{job_id}")
async def get_progress_stream(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_status = None
        last_progress = -1
        last_message = ""

        while True:
            job = jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            # Yield update only if something changed
            if (job.status != last_status or
                    job.progress != last_progress or
                    job.message != last_message):

                last_status = job.status
                last_progress = job.progress
                last_message = job.message

                data = {
                    "status": job.status,
                    "progress": job.progress,
                    "message": job.message,
                    "error": job.error
                }
                yield f"data: {json.dumps(data)}\n\n"

            if job.status in ["completed", "failed"]:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/clips/{job_id}")
async def get_job_clips(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job is not completed yet")
    return {"clips": job.clips}


@app.get("/api/video/{job_id}/{clip_filename}")
async def get_video_clip(job_id: str, clip_filename: str):
    # Sanitize inputs to prevent directory traversal
    if ".." in job_id or ".." in clip_filename:
        raise HTTPException(status_code=400, detail="Invalid path")

    path = os.path.join("output", job_id, clip_filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Video clip not found")

    # FileResponse natively supports range-requests in Starlette/FastAPI
    return FileResponse(path, media_type="video/mp4")


# Serve frontend static files — must be mounted AFTER all /api/* routes
# so API routes take precedence over the catch-all static handler.
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
