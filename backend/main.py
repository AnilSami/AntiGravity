import os
import uuid
import json
import logging
import asyncio
import time
import shutil
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from job_manager import jobs, run_pipeline, JobStatus
from clipper import check_ffmpeg
from analyzer import get_video_id
from config import settings

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

# Load environment variables from .env file
load_dotenv()

# Thread-safe in-memory cache mapping YouTube URLs to job IDs
url_to_job_id = {}
cache_lock = asyncio.Lock()


async def cleanup_old_jobs():
    """Background task to delete old jobs and clip folders to save disk space."""
    while True:
        await asyncio.sleep(settings.JOB_CLEANUP_INTERVAL_SECS)
        logger.info("Running job cleanup check...")
        now = time.time()

        # 1. Purge old jobs from in-memory dictionary
        for job_id, job in list(jobs.items()):
            is_old = False
            if job.created_at > 0:
                elapsed = now - job.created_at
                if job.status in ["completed", "failed"]:
                    if elapsed > settings.JOB_TTL_COMPLETED_SECS:
                        is_old = True
                else:
                    if elapsed > settings.JOB_TTL_RUNNING_SECS:
                        is_old = True
            else:
                is_old = job.status in ["completed", "failed"]

            if is_old:
                jobs.pop(job_id, None)
                # Evict from URL cache
                for url, j_id in list(url_to_job_id.items()):
                    if j_id == job_id:
                        url_to_job_id.pop(url, None)
                logger.info(f"Purged old job {job_id} from memory and cache.")

        # 2. Clean up old or orphaned clip folders on disk
        output_dir = "output"
        if os.path.exists(output_dir):
            try:
                for folder_name in os.listdir(output_dir):
                    if folder_name in ["cache", "temp_subs", "clips"]:
                        continue
                    folder_path = os.path.join(output_dir, folder_name)
                    if os.path.isdir(folder_path):
                        # Never delete folders for jobs that are still running
                        existing_job = jobs.get(folder_name)
                        if existing_job and existing_job.status not in ["completed", "failed"]:
                            continue

                        mtime = os.path.getmtime(folder_path)
                        # Clean if orphaned (not in memory map) AND older than TTL,
                        # or if the job is done and modified > TTL ago
                        ttl = settings.JOB_TTL_COMPLETED_SECS
                        if (folder_name not in jobs and now - mtime > ttl) or \
                           (existing_job and existing_job.status in ["completed", "failed"] and now - mtime > ttl):
                            try:
                                shutil.rmtree(folder_path)
                                logger.info(f"Cleaned up expired/orphaned folder: {folder_path}")
                            except Exception as e:
                                logger.error(f"Failed to delete expired folder {folder_path}: {e}")
            except Exception as e:
                logger.error(f"Error listing output directory during cleanup: {e}")


def _run_auto_sync():
    """Called by APScheduler to auto-sync YouTube analytics in the background."""
    try:
        from youtube_service import sync_youtube_analytics
        result = sync_youtube_analytics()
        logger.info(f"[AutoSync] YouTube analytics sync completed: {result.get('synced', 0)} clips synced.")
    except Exception as e:
        logger.error(f"[AutoSync] YouTube analytics sync failed: {e}")


def validate_pipeline_imports() -> None:
    """
    Import every key pipeline module at startup to prevent running the server in a partially broken state.
    Raises RuntimeError on failure.
    """
    modules_to_validate = [
        "music_selector",
        "analyzer",
        "clipper",
        "job_manager",
        "upload_package",
        "subtitle_detector",
        "analytics_repository"
    ]
    logger.info("Starting pipeline module validation...")
    import importlib
    for mod_name in modules_to_validate:
        try:
            importlib.import_module(mod_name)
            logger.info(f"Successfully validated/imported pipeline module: {mod_name}")
        except Exception as e:
            error_msg = f"CRITICAL: Failed to import pipeline module '{mod_name}' at startup: {e}"
            logger.critical(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
    logger.info("All pipeline modules successfully validated.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and graceful shutdown."""
    # --- Startup ---
    settings.validate()
    validate_pipeline_imports()
    os.makedirs("output", exist_ok=True)
    cleanup_task = asyncio.create_task(cleanup_old_jobs())

    # Auto-sync YouTube analytics every N hours (configurable via YOUTUBE_SYNC_INTERVAL_HOURS)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_auto_sync,
        trigger=IntervalTrigger(hours=settings.YOUTUBE_SYNC_INTERVAL_HOURS),
        id="youtube_auto_sync",
        replace_existing=True,
        name="YouTube Analytics Auto-Sync"
    )
    scheduler.start()
    logger.info(
        f"Server started. Auto-sync scheduled every {settings.YOUTUBE_SYNC_INTERVAL_HOURS}h. "
        f"Output directory ready. Config validated."
    )
    yield
    # --- Shutdown ---
    scheduler.shutdown(wait=False)
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Server shutting down cleanly.")



# Create the FastAPI app — lifespan must be defined before this line
app = FastAPI(title="YouTube Smart Clip Extractor API", lifespan=lifespan)

# Enable CORS — origins driven by ALLOWED_ORIGINS env var (no wildcard in beta/production)
logger.info(f"CORS allow-list: {settings.ALLOWED_ORIGINS}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class AnalyzeRequest(BaseModel):
    url: str
    gemini_api_key: Optional[str] = None
    num_clips: Optional[int] = None
    subtitle_style: Optional[str] = "kinetic"
    creator_preset: Optional[str] = "custom"
    font_name: Optional[str] = "Anton"
    font_size: Optional[int] = 75
    pop_scale: Optional[float] = 1.18
    pop_duration: Optional[int] = 260
    primary_color: Optional[str] = "#FFFFFF"
    highlight_color: Optional[str] = "#FFD400"
    outline_color: Optional[str] = "#000000"
    outline_thickness: Optional[int] = 4
    shadow_depth: Optional[int] = 2
    debug_camera_tracking: Optional[bool] = False
    force_refresh: Optional[bool] = False
    bypass_camera_qa: Optional[bool] = False


@app.get("/api/status")
async def health_check():
    """
    Health-check endpoint used by Railway (and any load balancer) to verify the
    server is up and ready to accept requests.
    Returns 200 OK when the server is healthy.
    """
    return {
        "status": "ok",
        "version": "2.0.0",
        "environment": settings.APP_ENV,
        "ffmpeg": check_ffmpeg(),
    }


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

    if request.num_clips is not None and (request.num_clips < 1 or request.num_clips > 50):
        raise HTTPException(
            status_code=400,
            detail="Number of clips must be between 1 and 50."
        )

    try:
        video_id = get_video_id(request.url)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YouTube URL format: {str(e)}"
        )

    async with cache_lock:
        existing_job_id = url_to_job_id.get(video_id)
        if existing_job_id:
            existing_job = jobs.get(existing_job_id)
            if existing_job and existing_job.status not in ["failed"]:
                logger.info(f"Reusing existing job {existing_job_id} for Video ID: {video_id}")
                return {"job_id": existing_job_id}
            else:
                url_to_job_id.pop(video_id, None)

        job_id = str(uuid.uuid4())
        url_to_job_id[video_id] = job_id
        logger.info(f"Queuing new job {job_id} for Video ID: {video_id}")

        # Initialize job status
        jobs[job_id] = JobStatus(
            id=job_id,
            status="pending",
            progress=0,
            message="Initializing job...",
            created_at=time.time()
        )

    # Launch processing in background
    background_tasks.add_task(
        run_pipeline,
        job_id,
        request.url,
        api_key,
        request.num_clips,
        request.subtitle_style,
        request.font_name,
        request.font_size,
        request.pop_scale,
        request.pop_duration,
        request.primary_color,
        request.highlight_color,
        request.outline_color,
        request.outline_thickness,
        request.shadow_depth,
        request.creator_preset,
        request.debug_camera_tracking,
        request.force_refresh,
        request.bypass_camera_qa
    )

    return {"job_id": job_id}


@app.get("/api/progress/{job_id}")
async def get_progress_stream(job_id: str, request: Request):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_status = None
        last_progress = -1
        last_message = ""

        while True:
            if await request.is_disconnected():
                logger.info(f"Client disconnected from progress stream for job {job_id}")
                break

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


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    return {
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error
    }


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
    import re
    if not re.match(r"^[a-zA-Z0-9\-]+$", job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", clip_filename) or clip_filename.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid clip filename format")

    base_dir = os.path.abspath("output")
    path = os.path.abspath(os.path.join(base_dir, job_id, clip_filename))
    if not path.startswith(base_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(path):
        # Fallback to shared clips directory for Phase 24
        fallback_path = os.path.abspath(os.path.join(base_dir, "clips", clip_filename))
        if fallback_path.startswith(base_dir) and os.path.exists(fallback_path):
            path = fallback_path
        else:
            raise HTTPException(status_code=404, detail="Video clip not found")

    # FileResponse natively supports range-requests in Starlette/FastAPI
    return FileResponse(path, media_type="video/mp4")



class AnalyticsSubmitRequest(BaseModel):
    clip_id: str
    platform: str
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    watch_time: float = Field(default=0.0, ge=0.0)
    retention: float = Field(default=0.0, ge=0.0)
    upload_date: str

class FeedbackSubmitRequest(BaseModel):
    clip_id: str
    feedback: str # "Great", "Good", "Average", "Poor"

class ActionSubmitRequest(BaseModel):
    clip_id: str
    selected: Optional[bool] = None
    rejected: Optional[bool] = None
    published: Optional[bool] = None

@app.post("/api/analytics/submit")
async def submit_analytics(request: AnalyticsSubmitRequest):
    import re
    if not re.match(r"^[a-zA-Z0-9\-]+$", request.clip_id):
        raise HTTPException(status_code=400, detail="Invalid clip ID format")
    try:
        from analytics_repository import db as analytics_db
        analytics_db.update_clip_analytics(
            clip_id=request.clip_id,
            platform=request.platform,
            views=request.views,
            likes=request.likes,
            comments=request.comments,
            shares=request.shares,
            watch_time=request.watch_time,
            retention=request.retention,
            upload_date=request.upload_date
        )
        
        # Trigger Reflection Agent and Creator Brain update
        try:
            from personal_ai.reflection.reflector import run_reflection_agent
            run_reflection_agent(
                clip_id=request.clip_id,
                actual_views=request.views or 0,
                actual_retention=request.retention or 0.0,
                actual_likes=request.likes or 0
            )
        except Exception as ref_err:
            logger.warning(f"Failed to run Reflection Agent: {ref_err}")

        return {"status": "success", "message": "Analytics metrics and AI reflections updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analytics/feedback")
async def submit_feedback(request: FeedbackSubmitRequest):
    if request.feedback not in ["Great", "Good", "Average", "Poor"]:
        raise HTTPException(status_code=400, detail="Invalid feedback rating. Must be Great, Good, Average, or Poor.")
    import re
    if not re.match(r"^[a-zA-Z0-9\-]+$", request.clip_id):
        raise HTTPException(status_code=400, detail="Invalid clip ID format")
    try:
        from analytics_repository import db as analytics_db
        analytics_db.submit_clip_feedback(clip_id=request.clip_id, feedback=request.feedback)
        return {"status": "success", "message": "Creator feedback recorded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analytics/action")
async def submit_action(request: ActionSubmitRequest):
    import re
    if not re.match(r"^[a-zA-Z0-9\-]+$", request.clip_id):
        raise HTTPException(status_code=400, detail="Invalid clip ID format")
    try:
        from analytics_repository import db as analytics_db
        analytics_db.update_creator_action(
            clip_id=request.clip_id,
            selected=request.selected,
            rejected=request.rejected,
            published=request.published
        )
        
        # Trigger feedback learning engine weight adjustments & profile rebuild
        if request.selected or request.rejected:
            try:
                from learning_engine import adjust_weights_on_creator_action
                from creator_profile import rebuild_creator_profile
                adjust_weights_on_creator_action(
                    clip_id=request.clip_id,
                    selected=bool(request.selected),
                    rejected=bool(request.rejected)
                )
                rebuild_creator_profile()
            except Exception as learn_err:
                logger.warning(f"Failed to run feedback learning engine update: {learn_err}")
                
        return {"status": "success", "message": "Creator actions and AI learning updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/youtube/sync")
async def sync_youtube():
    try:
        from youtube_service import sync_youtube_analytics
        result = sync_youtube_analytics()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/correlation")
async def get_correlations():
    try:
        from analytics_engine import get_performance_correlations
        correlations = get_performance_correlations()
        return {"status": "success", "correlations": correlations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/report")
async def get_reports():
    try:
        from analytics_engine import generate_model_improvement_report, generate_creator_disagreement_report
        improvement_report, _ = generate_model_improvement_report()
        disagreement_report, _ = generate_creator_disagreement_report()
        return {
            "status": "success",
            "model_improvement": improvement_report,
            "creator_disagreement": disagreement_report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/youtube/export")
async def export_youtube_dataset():
    try:
        from analytics_engine import compile_analytics_export
        csv_path = compile_analytics_export()
        if not os.path.exists(csv_path):
            raise HTTPException(status_code=404, detail="Dataset file not found after generation.")
        return FileResponse(
            csv_path,
            media_type="text/csv",
            filename="analytics_export.csv",
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PublishRequest(BaseModel):
    title: str
    description: str
    tags: Optional[list[str]] = Field(default_factory=list)

@app.get("/api/youtube/status")
async def youtube_status():
    try:
        from youtube_service import get_valid_credentials, is_mock_mode, _save_tokens_to_json
        from analytics_repository import db as analytics_db
        from googleapiclient.discovery import build
        
        creds = get_valid_credentials()
        connected = creds is not None
        channel_name = None
        channel_id = None
        subscriber_count = 0
        video_count = 0
        
        if connected:
            creds_info = analytics_db.get_credentials("youtube")
            if creds_info:
                channel_name = creds_info.get("channel_name")
                channel_id = creds_info.get("channel_id")
                
            if is_mock_mode() or (hasattr(creds, "token") and creds.token == "mock_valid"):
                subscriber_count = 12500
                video_count = 42
                if not channel_name:
                    channel_name = "Mock Shorts Creator"
                    channel_id = "mock_channel_id_123"
            else:
                try:
                    # Fetch live channel details from YouTube API
                    youtube = build("youtube", "v3", credentials=creds)
                    res = youtube.channels().list(
                        part="snippet,statistics",
                        mine=True
                    ).execute()
                    if "items" in res and len(res["items"]) > 0:
                        item = res["items"][0]
                        channel_name = item["snippet"]["title"]
                        channel_id = item["id"]
                        stats = item.get("statistics", {})
                        subscriber_count = int(stats.get("subscriberCount", 0))
                        video_count = int(stats.get("videoCount", 0))
                        
                        # Update stored values to keep them in sync
                        if creds_info:
                            analytics_db.save_credentials(
                                platform="youtube",
                                access_token=creds_info["access_token"],
                                refresh_token=creds_info["refresh_token"],
                                token_expiry=creds_info["token_expiry"],
                                channel_name=channel_name,
                                channel_id=channel_id
                            )
                            _save_tokens_to_json(
                                access_token=creds.token,
                                refresh_token=creds.refresh_token or "",
                                token_expiry=creds.expiry.timestamp() if creds.expiry else time.time() + 3600.0,
                                channel_name=channel_name,
                                channel_id=channel_id
                            )
                except Exception as api_err:
                    logger.warning(f"Failed to fetch live YouTube stats: {api_err}")
                    
        return {
            "connected": connected,
            "channel_name": channel_name,
            "channel_id": channel_id,
            "subscriber_count": subscriber_count,
            "video_count": video_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _resolve_and_validate_redirect_uri(request: Request) -> str:
    """Resolve the OAuth redirect URI and validate it against ALLOWED_ORIGINS."""
    base_url = str(request.base_url)
    redirect_uri = f"{base_url.rstrip('/')}/api/youtube/callback"
    env_redirect = settings.YOUTUBE_REDIRECT_URI
    if env_redirect:
        redirect_uri = env_redirect

    # Validate redirect URI origin against the CORS allow-list
    from urllib.parse import urlparse
    parsed = urlparse(redirect_uri)
    redirect_origin = f"{parsed.scheme}://{parsed.netloc}"
    if redirect_origin not in settings.ALLOWED_ORIGINS:
        raise HTTPException(
            status_code=400,
            detail=f"Redirect URI origin '{redirect_origin}' is not in the allowed origins list. "
                   f"Allowed: {settings.ALLOWED_ORIGINS}"
        )
    return redirect_uri


@app.get("/api/youtube/auth")
async def youtube_auth(request: Request):
    try:
        redirect_uri = _resolve_and_validate_redirect_uri(request)

        from youtube_service import get_auth_url, store_oauth_state
        auth_url, state = get_auth_url(redirect_uri)
        store_oauth_state(state)
        from fastapi.responses import JSONResponse
        return JSONResponse({"auth_url": auth_url, "redirect_uri_used": redirect_uri})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/youtube/callback")
async def youtube_callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error:
        return RedirectResponse(f"/?error={error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state parameter. Possible CSRF attack.")
        
    # Validate CSRF state token (single-use — consumed on validation)
    from youtube_service import validate_oauth_state
    if not validate_oauth_state(state):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state parameter. This may indicate a CSRF attack or an expired authorization session. Please try connecting again."
        )
        
    try:
        redirect_uri = _resolve_and_validate_redirect_uri(request)
            
        from youtube_service import handle_oauth_callback
        handle_oauth_callback(code, redirect_uri)
        return RedirectResponse("/?tab=youtube-tab")
    except HTTPException:
        raise
    except Exception as e:
        return RedirectResponse(f"/?error={str(e)}")

@app.post("/api/youtube/publish/{clip_id}")
async def publish_clip(clip_id: str, request_data: PublishRequest):
    import re
    if not re.match(r"^[a-zA-Z0-9\-]+$", clip_id):
        raise HTTPException(status_code=400, detail="Invalid clip ID format")
    try:
        from youtube_service import publish_clip_to_youtube
        
        # Locate the clip path — prefer _with_music.mp4 if available
        clip_path = None
        output_dir = "output"
        if os.path.exists(output_dir):
            # Check the shared clips directory first (with-music version)
            with_music_path = os.path.join("output", "clips", f"{clip_id}_with_music.mp4")
            if os.path.exists(with_music_path):
                clip_path = with_music_path
            else:
                # Fall back to job-specific folder (original clip)
                for job_folder in os.listdir(output_dir):
                    job_path = os.path.join(output_dir, job_folder)
                    if os.path.isdir(job_path):
                        potential_path = os.path.join(job_path, f"clip_{clip_id}.mp4")
                        if os.path.exists(potential_path):
                            clip_path = potential_path
                            break
                        
        if not clip_path:
            raise HTTPException(status_code=404, detail=f"Generated clip file not found on disk for ID {clip_id}.")
            
        yt_id = publish_clip_to_youtube(
            clip_id=clip_id,
            video_path=clip_path,
            title=request_data.title,
            description=request_data.description,
            tags=request_data.tags
        )
        return {"status": "success", "youtube_video_id": yt_id, "message": "Clip successfully published to YouTube."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/youtube/upload/{clip_id}")
async def upload_clip(clip_id: str):
    import re
    if not re.match(r"^[a-zA-Z0-9\-]+$", clip_id):
        raise HTTPException(status_code=400, detail="Invalid clip ID format")
    try:
        from youtube_service import upload_clip_to_youtube
        res = upload_clip_to_youtube(clip_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/youtube/upload/progress/{clip_id}")
async def upload_progress(clip_id: str):
    try:
        from youtube_service import _upload_progress
        return {"progress": _upload_progress.get(clip_id, 0)}
    except Exception:
        return {"progress": 0}

@app.get("/api/youtube/dashboard")
async def get_youtube_dashboard():
    try:
        from analytics_repository import db as analytics_db
        from youtube_service import get_valid_credentials
        from analytics_engine import generate_model_improvement_report, generate_creator_disagreement_report
        
        creds = get_valid_credentials()
        creds_info = analytics_db.get_credentials("youtube")
        
        connected = creds is not None
        channel_name = creds_info["channel_name"] if (connected and creds_info) else None
        
        records = analytics_db.get_all_records()
        published_clips = []
        for r in records:
            if r.get("published") == 1:
                clip_id = r["clip_id"]
                snapshots = analytics_db.get_analytics_snapshots(clip_id)
                snap_list = []
                for s in snapshots:
                    snap_list.append({
                        "snapshot_time": s["snapshot_time"],
                        "views": s["views"],
                        "likes": s["likes"],
                        "comments": s["comments"],
                        "watch_time": s["watch_time"],
                        "retention": s["retention"]
                    })
                
                try:
                    tags = json.loads(r.get("shorts_tags")) if r.get("shorts_tags") else []
                except Exception:
                    tags = []
                    
                published_clips.append({
                    "clip_id": clip_id,
                    "video_id": r["video_id"],
                    "title": r.get("title") or f"Clip {clip_id}",
                    "reason": r.get("reason") or "Highlight",
                    "shorts_title": r.get("shorts_title") or f"Clip {clip_id} #Shorts",
                    "shorts_description": r.get("shorts_description") or "",
                    "shorts_tags": tags,
                    "duration": r.get("duration") or 30.0,
                    "virality_score": r["virality_score"],
                    "views": r.get("views") or 0,
                    "likes": r.get("likes") or 0,
                    "comments": r.get("comments") or 0,
                    "watch_time": r.get("watch_time") or 0.0,
                    "retention": r.get("retention") or 0.0,
                    "upload_date": r.get("upload_date") or "",
                    "snapshots": snap_list
                })
                
        # Generate reports
        improvement_report, _ = generate_model_improvement_report()
        disagreement_report, _ = generate_creator_disagreement_report()
        
        return {
            "status": "success",
            "connected": connected,
            "channel_name": channel_name,
            "published_clips": published_clips,
            "last_sync_time": analytics_db.get_last_sync_time(),
            "reports": {
                "model_improvement": improvement_report,
                "creator_disagreement": disagreement_report
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/experiments")
async def get_experiments():
    try:
        from analytics_engine import analyze_ab_test, generate_experiment_report
        generate_experiment_report() # updates md and json deliverables
        results = analyze_ab_test()
        return {"status": "success", "experiments": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analytics/seed")
async def seed_experiments():
    try:
        from analytics_engine import seed_experiment_data
        result = seed_experiment_data()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/transcripts")
async def get_transcript_metrics():
    try:
        from analytics_repository import db as analytics_db
        metrics = analytics_db.get_transcript_metrics_summary()
        return {"status": "success", "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/personal/profile")
async def get_personal_profile(version: Optional[str] = "default"):
    """Fetches the Personalized Creator AI profile containing style and scoring weights."""
    try:
        from creator_profile import get_creator_profile
        profile = get_creator_profile(version)
        return {"status": "success", "profile": profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/personal/profile/rebuild")
async def rebuild_personal_profile(version: Optional[str] = "default"):
    """Forces rebuild of the creator profile based on latest database records."""
    try:
        from creator_profile import rebuild_creator_profile
        profile = rebuild_creator_profile(version)
        return {"status": "success", "profile": profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/personal/dashboard")
async def get_personal_dashboard_data():
    """Exposes structured JSON data for the Personal AI strategist dashboard."""
    try:
        from analytics_repository import db as analytics_db
        conn = analytics_db._get_connection()
        predictions = []
        reflections = []
        lessons = []
        weights = {}
        
        try:
            with conn:
                cursor = conn.cursor()
                
                # 1. Predictions & Reflections History
                cursor.execute("""
                    SELECT p.clip_id, p.predicted_score, p.detailed_predictions, p.target_audience, p.reasoning, p.created_at,
                           r.views_diff, r.retention_diff, r.evaluation, r.weight_adjustments
                    FROM creator_predictions p
                    LEFT JOIN creator_reflections r ON p.clip_id = r.clip_id
                    ORDER BY p.created_at DESC
                """)
                for row in cursor.fetchall():
                    try:
                        detailed = json.loads(row[2])
                    except Exception:
                        detailed = {}
                        
                    try:
                        weight_adj = json.loads(row[9]) if row[9] else {}
                    except Exception:
                        weight_adj = {}

                    predictions.append({
                        "clip_id": row[0],
                        "predicted_score": row[1],
                        "detailed_predictions": detailed,
                        "target_audience": row[3],
                        "reasoning": row[4],
                        "created_at": row[5],
                        "actual_performance": {
                            "views_diff": row[6] if row[6] is not None else 0,
                            "retention_diff": row[7] if row[7] is not None else 0.0,
                            "evaluation": row[8] if row[8] is not None else "pending",
                            "weight_adjustments": weight_adj
                        }
                    })

                # 2. Lessons Learned
                cursor.execute("SELECT lesson_id, type, concept, description, created_at FROM creator_lessons ORDER BY created_at DESC")
                for row in cursor.fetchall():
                    lessons.append({
                        "lesson_id": row[0],
                        "type": row[1],
                        "concept": row[2],
                        "description": row[3],
                        "created_at": row[4]
                    })

                # 3. Current Virality Weights
                cursor.execute("SELECT virality_weights FROM creator_profile_state ORDER BY last_updated DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    weights = json.loads(row[0])
                else:
                    from creator_profile import DEFAULT_VIRALITY_WEIGHTS
                    weights = DEFAULT_VIRALITY_WEIGHTS
        finally:
            conn.close()

        # Compute error and confidence trends over time
        confidence_trend = []
        for p in reversed(predictions):
            actual = p["actual_performance"]
            if actual["evaluation"] != "pending":
                error_magnitude = abs(actual["views_diff"]) / 1000.0 + abs(actual["retention_diff"])
                confidence_trend.append({
                    "clip_id": p["clip_id"],
                    "created_at": p["created_at"],
                    "error_score": round(error_magnitude, 3),
                    "evaluation": actual["evaluation"]
                })

        return {
            "status": "success",
            "weights": weights,
            "predictions_history": predictions,
            "lessons_learned": lessons,
            "confidence_trend": confidence_trend
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve frontend static files — must be mounted AFTER all /api/* routes
# so API routes take precedence over the catch-all static handler.
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
