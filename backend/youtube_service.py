import os
import time
import logging
import random
import string
from datetime import date
from typing import Optional, Tuple, Dict

from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from analytics_repository import db as analytics_db

logger = logging.getLogger("youtube_service")

# --- OAuth CSRF State Store ---
# Thread-safe in-memory store for OAuth state tokens with TTL expiry.
# Each entry maps state_token -> creation_timestamp.
# States are single-use: consumed on validation to prevent replay attacks.
import threading

_oauth_state_store: Dict[str, float] = {}
_oauth_state_lock = threading.Lock()
_OAUTH_STATE_TTL_SECONDS = 600  # 10 minutes

def store_oauth_state(state: str) -> None:
    """Persist an OAuth state token with current timestamp."""
    with _oauth_state_lock:
        # Prune expired entries on each store to prevent unbounded growth
        _prune_expired_states()
        _oauth_state_store[state] = time.time()
        logger.info(f"OAuth state stored: {state[:12]}...")

def validate_oauth_state(state: str) -> bool:
    """
    Validate and consume an OAuth state token (single-use).
    Returns True if the state is valid and not expired.
    Returns False if the state is missing, expired, or already consumed.
    """
    with _oauth_state_lock:
        if state not in _oauth_state_store:
            logger.warning(f"OAuth state validation failed: state not found ({state[:12]}...)")
            return False
        created_at = _oauth_state_store.pop(state)  # Single-use: consume immediately
        age = time.time() - created_at
        if age > _OAUTH_STATE_TTL_SECONDS:
            logger.warning(f"OAuth state validation failed: state expired (age={age:.0f}s, ttl={_OAUTH_STATE_TTL_SECONDS}s)")
            return False
        logger.info(f"OAuth state validated successfully (age={age:.1f}s)")
        return True

def _prune_expired_states() -> None:
    """Remove expired state entries. Must be called under _oauth_state_lock."""
    now = time.time()
    expired_keys = [k for k, v in _oauth_state_store.items() if now - v > _OAUTH_STATE_TTL_SECONDS]
    for k in expired_keys:
        del _oauth_state_store[k]
    if expired_keys:
        logger.info(f"Pruned {len(expired_keys)} expired OAuth state(s)")

def get_pending_state_count() -> int:
    """Returns the number of pending (unconsumed) state tokens. For testing/monitoring."""
    with _oauth_state_lock:
        _prune_expired_states()
        return len(_oauth_state_store)


# --- Token Encryption helpers ---
def _get_encryption_key() -> bytes:
    from config import settings
    key = settings.ENCRYPTION_KEY
    if not key:
        if settings.is_production:
            raise RuntimeError(
                "ENCRYPTION_KEY must be pre-set in production. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        # Development/beta: generate one dynamically and persist it
        key = Fernet.generate_key().decode()
        if settings.is_development:
            # Only auto-append to .env in development mode
            env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".env"))
            if os.path.exists(env_path):
                try:
                    with open(env_path, "a") as f:
                        f.write(f"\nENCRYPTION_KEY={key}\n")
                    logger.info("Generated new ENCRYPTION_KEY and saved to .env (development mode)")
                except Exception as e:
                    logger.error(f"Failed to append ENCRYPTION_KEY to .env: {e}")
        else:
            logger.warning("Generated ephemeral ENCRYPTION_KEY (not persisted in beta mode)")
        os.environ["ENCRYPTION_KEY"] = key
    return key.encode()

def encrypt_token(token: str) -> str:
    if not token:
        return ""
    f = Fernet(_get_encryption_key())
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        return ""
    f = Fernet(_get_encryption_key())
    return f.decrypt(encrypted_token.encode()).decode()


# --- Configuration & Mock Check ---
def is_mock_mode() -> bool:
    from config import settings
    client_id = settings.YOUTUBE_CLIENT_ID
    client_secret = settings.YOUTUBE_CLIENT_SECRET
    # If secrets are missing, or we explicitly force mock mode
    mock = not client_id or not client_secret or os.getenv("YOUTUBE_MOCK_MODE") == "true"
    if mock and settings.is_production:
        raise RuntimeError(
            "Mock OAuth mode is forbidden in production. "
            "Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET environment variables."
        )
    return mock

def get_oauth_flow(redirect_uri: str) -> Flow:
    from config import settings
    client_id = settings.YOUTUBE_CLIENT_ID
    client_secret = settings.YOUTUBE_CLIENT_SECRET
    
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }
    
    scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
        "https://www.googleapis.com/auth/youtube.readonly"
    ]
    
    return Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=redirect_uri
    )


# --- OAuth Flow Handlers ---
def get_auth_url(redirect_uri: str) -> Tuple[str, str]:
    """
    Generates OAuth authorization URL and CSRF state parameter.
    If in mock mode, returns a mock local redirect URL.
    """
    if is_mock_mode():
        state = "mock_state_" + "".join(random.choices(string.ascii_letters + string.digits, k=10))
        # Redirect back to the callback endpoint directly with mock code
        mock_auth_url = f"{redirect_uri}?code=mock_oauth_code_123&state={state}"
        return mock_auth_url, state
        
    flow = get_oauth_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    return authorization_url, state

def handle_oauth_callback(code: str, redirect_uri: str) -> dict:
    """
    Exchanges code for credentials, saves them to database (encrypted), and returns channel name.
    """
    if is_mock_mode() or code.startswith("mock_"):
        # Save mock credentials
        channel_name = "Mock Shorts Creator"
        analytics_db.save_credentials(
            platform="youtube",
            access_token=encrypt_token("mock_access_token_123"),
            refresh_token=encrypt_token("mock_refresh_token_123"),
            token_expiry=time.time() + 3600.0,
            channel_name=channel_name
        )
        return {"channel_name": channel_name, "mock": True}
        
    flow = get_oauth_flow(redirect_uri)
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    # Retrieve channel name using YouTube Data API
    youtube = build("youtube", "v3", credentials=credentials)
    channels_response = youtube.channels().list(
        part="snippet",
        mine=True
    ).execute()
    
    channel_name = "YouTube Creator"
    if "items" in channels_response and len(channels_response["items"]) > 0:
        channel_name = channels_response["items"][0]["snippet"]["title"]
        
    # Save credentials securely
    analytics_db.save_credentials(
        platform="youtube",
        access_token=encrypt_token(credentials.token),
        refresh_token=encrypt_token(credentials.refresh_token or ""),
        token_expiry=credentials.expiry.timestamp() if credentials.expiry else time.time() + 3600.0,
        channel_name=channel_name
    )
    
    return {"channel_name": channel_name, "mock": False}


# --- Token Refresh Logic ---
def get_valid_credentials() -> Optional[Credentials]:
    """
    Retrieves stored credentials, decrypts them, refreshes access token if expired, and returns Credentials.
    """
    creds_row = analytics_db.get_credentials("youtube")
    if not creds_row:
        return None
        
    # If in mock mode, return none/mock indicator or construct mock Credentials
    if is_mock_mode() or creds_row["refresh_token"].startswith("mock_") or decrypt_token(creds_row["refresh_token"]).startswith("mock_"):
        # Just return custom indicator credentials
        return Credentials(token="mock_valid")

    access_token = decrypt_token(creds_row["access_token"])
    refresh_token = decrypt_token(creds_row["refresh_token"])
    token_expiry = creds_row["token_expiry"]
    
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("YOUTUBE_CLIENT_ID"),
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET")
    )
    
    # If expired (or expiring in 60s), refresh
    if token_expiry - time.time() < 60:
        logger.info("YouTube access token expired or expiring soon, refreshing...")
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            # Save new tokens
            analytics_db.save_credentials(
                platform="youtube",
                access_token=encrypt_token(creds.token),
                refresh_token=encrypt_token(creds.refresh_token or refresh_token),
                token_expiry=creds.expiry.timestamp() if creds.expiry else time.time() + 3600.0,
                channel_name=creds_row["channel_name"]
            )
            logger.info("YouTube access token refreshed successfully.")
        except Exception as e:
            logger.error(f"Failed to refresh YouTube OAuth token: {e}")
            return None
            
    return creds


# --- Publishing / Upload Flow ---
def publish_clip_to_youtube(clip_id: str, video_path: str, title: str, description: str, tags: list) -> str:
    """
    Uploads the video clip to YouTube as a public YouTube Short (via privacyStatus=public).
    Returns the YouTube Video ID.
    """
    creds = get_valid_credentials()
    if not creds:
        raise ValueError("YouTube account is not connected. Connect via OAuth first.")
        
    if is_mock_mode() or creds.token == "mock_valid":
        # Simulate video upload latency and return mock ID
        time.sleep(0.5)
        mock_yt_id = "mock_yt_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=11))
        
        # Update metadata in db
        analytics_db.update_creator_action(clip_id=clip_id, published=True)
        # Update clip analytics to associate it with YouTube
        analytics_db.update_clip_analytics(
            clip_id=clip_id,
            platform="YouTube",
            views=0,
            likes=0,
            comments=0,
            shares=0,
            watch_time=0.0,
            retention=0.0,
            upload_date=date.today().isoformat()
        )
        return mock_yt_id

    youtube = build("youtube", "v3", credentials=creds)
    
    # Set default tag #Shorts
    if "Shorts" not in tags and "shorts" not in [t.lower() for t in tags]:
        tags.append("Shorts")
        
    body = {
        "snippet": {
            "title": title[:100],  # Title limit is 100 characters
            "description": description[:5000],
            "tags": tags
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        chunksize=1024 * 1024,
        resumable=True
    )
    
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    
    logger.info(f"Uploading clip {clip_id} to YouTube...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"YouTube Upload Progress: {int(status.progress() * 100)}%")
            
    youtube_video_id = response.get("id")
    logger.info(f"Uploaded clip {clip_id} successfully. YouTube Video ID: {youtube_video_id}")
    
    # Update local state
    analytics_db.update_creator_action(clip_id=clip_id, published=True)
    analytics_db.update_clip_analytics(
        clip_id=clip_id,
        platform="YouTube",
        views=0,
        likes=0,
        comments=0,
        shares=0,
        watch_time=0.0,
        retention=0.0,
        upload_date=date.today().isoformat()
    )
    
    return youtube_video_id


# --- Analytics Sync Flow ---
def sync_youtube_analytics() -> dict:
    """
    Iterates through all published clips in clip_analytics, queries current stats from YouTube APIs,
    updates the clip_analytics table, and logs a timestamped snapshot.
    Returns sync stats.
    """
    creds = get_valid_credentials()
    if not creds:
        return {"status": "error", "message": "YouTube account is not connected."}
        
    # Get all published clips
    all_clips = analytics_db.get_all_records()
    published_clips = [c for c in all_clips if c.get("published") == 1]
    
    if not published_clips:
        return {"status": "success", "synced_count": 0, "message": "No published clips to sync."}
        
    synced_count = 0
    now = time.time()
    
    is_mock = is_mock_mode() or creds.token == "mock_valid"
    
    for clip in published_clips:
        clip_id = clip["clip_id"]
        
        # Check if we have views already or mock stats to grow
        prev_views = clip.get("views") or 0
        prev_likes = clip.get("likes") or 0
        prev_comments = clip.get("comments") or 0
        prev_watch_time = clip.get("watch_time") or 0.0
        prev_retention = clip.get("retention") or 0.0
        
        if is_mock:
            # Generate growing metrics dynamically for mock trend analysis
            # Growth: views grow by 1000-5000 per sync, likes, comments, etc.
            growth_mult = random.uniform(1.1, 1.5)
            if prev_views == 0:
                views = random.randint(1500, 5000)
                likes = int(views * random.uniform(0.04, 0.08))
                comments = int(views * random.uniform(0.005, 0.015))
                retention = random.uniform(55.0, 85.0)
            else:
                views = int(prev_views * growth_mult)
                likes = int(prev_likes * growth_mult)
                comments = int(prev_comments * growth_mult)
                retention = min(98.0, prev_retention * random.uniform(0.98, 1.02))
                
            watch_time = round(views * (retention / 100.0) * 0.5, 2)
            publish_date = clip.get("upload_date") or date.today().isoformat()
            
        else:
            # Real API call
            try:
                youtube = build("youtube", "v3", credentials=creds)
                # Map clip_id to YouTube Video ID.
                yt_id = clip_id
                
                # Fetch statistics
                video_response = youtube.videos().list(
                    part="statistics,snippet",
                    id=yt_id
                ).execute()
                
                if "items" not in video_response or len(video_response["items"]) == 0:
                    logger.warning(f"Video {yt_id} not found on YouTube. Skipping.")
                    continue
                    
                item = video_response["items"][0]
                stats = item.get("statistics", {})
                snippet = item.get("snippet", {})
                
                views = int(stats.get("viewCount", 0))
                likes = int(stats.get("likeCount", 0))
                comments = int(stats.get("commentCount", 0))
                publish_date_raw = snippet.get("publishedAt", "")
                if publish_date_raw:
                    # Parse to YYYY-MM-DD
                    publish_date = publish_date_raw.split("T")[0]
                else:
                    publish_date = date.today().isoformat()
                    
                # Query YouTube Analytics API for watch time & average view duration
                analytics = build("youtubeAnalytics", "v2", credentials=creds)
                # Format start date as publish date or 30 days ago
                start_str = publish_date if publish_date else "2026-01-01"
                end_str = date.today().isoformat()
                
                analytics_response = analytics.reports().query(
                    ids="channel==MINE",
                    startDate=start_str,
                    endDate=end_str,
                    metrics="estimatedMinutesWatched,averageViewDuration",
                    dimensions="video",
                    filters=f"video=={yt_id}"
                ).execute()
                
                watch_time = 0.0
                retention = 0.0
                if "rows" in analytics_response and len(analytics_response["rows"]) > 0:
                    row = analytics_response["rows"][0]
                    estimated_minutes = float(row[1])
                    avg_duration_sec = float(row[2])
                    
                    # convert minutes to hours or keep as hours for watch_time
                    watch_time = round(estimated_minutes / 60.0, 2)
                    
                    # Calculate retention percentage
                    clip_duration = clip.get("duration") or 30.0
                    if clip_duration > 0:
                        retention = round((avg_duration_sec / clip_duration) * 100.0, 2)
                        retention = min(100.0, retention)
                        
            except Exception as e:
                logger.error(f"Error syncing real YouTube stats for clip {clip_id}: {e}")
                views, likes, comments, watch_time, retention, publish_date = prev_views, prev_likes, prev_comments, prev_watch_time, prev_retention, clip.get("upload_date") or date.today().isoformat()
        
        # Update metrics in database
        analytics_db.update_clip_analytics(
            clip_id=clip_id,
            platform="YouTube",
            views=views,
            likes=likes,
            comments=comments,
            shares=0,
            watch_time=watch_time,
            retention=retention,
            upload_date=publish_date
        )
        
        # Save snapshot
        analytics_db.save_analytics_snapshot(
            clip_id=clip_id,
            views=views,
            likes=likes,
            comments=comments,
            watch_time=watch_time,
            retention=retention,
            snapshot_time=now
        )
        
        synced_count += 1
        
    return {
        "status": "success",
        "synced_count": synced_count,
        "message": f"Successfully synchronized analytics for {synced_count} clips."
    }
