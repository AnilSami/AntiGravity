import os
import json
import csv
import time
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure the test server origin is allowed before app/config import
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://testserver")

from analytics_repository import db as analytics_db
from youtube_service import (
    encrypt_token,
    decrypt_token,
    sync_youtube_analytics
)
from analytics_engine import compile_analytics_export
from main import app

client = TestClient(app)

def test_token_encryption():
    test_token = "secrets-12345-youtube-key"
    encrypted = encrypt_token(test_token)
    assert encrypted != test_token
    assert len(encrypted) > len(test_token)
    
    decrypted = decrypt_token(encrypted)
    assert decrypted == test_token

def test_credentials_db_lifecycle():
    platform = "youtube_test"
    # Clean first
    analytics_db.delete_credentials(platform)
    
    # Save credentials
    access = "access_token_val"
    refresh = "refresh_token_val"
    expiry = time.time() + 1800
    channel = "Test Channel"
    
    analytics_db.save_credentials(platform, access, refresh, expiry, channel)
    
    # Retrieve
    creds = analytics_db.get_credentials(platform)
    assert creds is not None
    assert creds["platform"] == platform
    assert creds["access_token"] == access
    assert creds["refresh_token"] == refresh
    assert creds["token_expiry"] == expiry
    assert creds["channel_name"] == channel
    
    # Delete
    analytics_db.delete_credentials(platform)
    creds_after = analytics_db.get_credentials(platform)
    assert creds_after is None

def test_analytics_snapshots():
    clip_id = "test_clip_snapshots"
    
    # Clear any previous snapshots
    conn = analytics_db.connect() if hasattr(analytics_db, "connect") else None
    if not conn:
        import sqlite3
        conn = sqlite3.connect(analytics_db.db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clip_analytics_snapshots WHERE clip_id = ?", (clip_id,))
    conn.commit()
    conn.close()
    
    # Save a series of snapshots
    t1 = time.time() - 3600
    t2 = time.time()
    
    analytics_db.save_analytics_snapshot(clip_id, views=100, likes=10, comments=2, watch_time=1.5, retention=50.0, snapshot_time=t1)
    analytics_db.save_analytics_snapshot(clip_id, views=250, likes=22, comments=5, watch_time=3.8, retention=48.5, snapshot_time=t2)
    
    # Fetch
    snaps = analytics_db.get_analytics_snapshots(clip_id)
    assert len(snaps) == 2
    assert snaps[0]["views"] == 100
    assert snaps[0]["snapshot_time"] == t1
    assert snaps[1]["views"] == 250
    assert snaps[1]["snapshot_time"] == t2

def test_compile_analytics_export():
    # Insert test data into clip_analytics
    clip_id = "test_export_clip_99"
    video_id = "test_video_99"
    virality_score = 8.5
    detailed_scores = {
        "hook_strength": 9,
        "first_3_second_hook": 8,
        "curiosity_gap": 7,
        "emotional_intensity": 8,
        "controversy": 5,
        "surprise": 6,
        "actionability": 7,
        "storytelling": 9
    }
    
    analytics_db.save_clip_metadata(
        video_id=video_id,
        clip_id=clip_id,
        virality_score=virality_score,
        detailed_scores=detailed_scores,
        experiment_id="exp_test",
        variant_id="A",
        scoring_version="v1",
        prompt_version="v1",
        weight_version="v1"
    )
    
    analytics_db.update_clip_analytics(
        clip_id=clip_id,
        platform="YouTube",
        views=1500,
        likes=120,
        comments=30,
        shares=0,
        watch_time=12.5,
        retention=68.2,
        upload_date="2026-06-18"
    )
    
    # Run compiler
    export_path = "output/test_export.csv"
    if os.path.exists(export_path):
        os.remove(export_path)
        
    compile_analytics_export(export_path)
    
    assert os.path.exists(export_path)
    
    # Read and verify CSV
    with open(export_path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        
        # Verify Headers
        headers = reader[0]
        assert "clip_id" in headers
        assert "virality_score" in headers
        assert "hook_strength" in headers
        assert "creator_selected" in headers
        assert "views" in headers
        
        # Find our row
        row = None
        for r in reader[1:]:
            if r[0] == clip_id:
                row = r
                break
                
        assert row is not None
        # Headers index mapping
        clip_idx = headers.index("clip_id")
        views_idx = headers.index("views")
        hook_idx = headers.index("hook_strength")
        virality_idx = headers.index("virality_score")
        
        assert row[clip_idx] == clip_id
        assert float(row[virality_idx]) == virality_score
        assert int(row[hook_idx]) == 9
        assert int(row[views_idx]) == 1500
        
    # Cleanup
    if os.path.exists(export_path):
        os.remove(export_path)

def test_api_routes_analytics():
    # Test dashboard route
    response = client.get("/api/youtube/dashboard")
    assert response.status_code == 200
    json_data = response.json()
    assert "status" in json_data
    assert json_data["status"] == "success"
    assert "connected" in json_data
    assert "published_clips" in json_data
    assert "reports" in json_data
    
    # Test export dataset download route
    response_export = client.get("/api/youtube/export")
    assert response_export.status_code == 200
    assert response_export.headers["content-type"] == "text/csv; charset=utf-8"
    
    # Test sync route
    # Let's seed mock credentials so sync doesn't exit immediately on no credentials
    analytics_db.save_credentials(
        platform="youtube",
        access_token=encrypt_token("mock_access"),
        refresh_token=encrypt_token("mock_refresh"),
        token_expiry=time.time() + 3600,
        channel_name="Mock Tester"
    )
    
    # Mark at least one clip as published
    clip_id = "test_sync_clip_101"
    analytics_db.save_clip_metadata(
        video_id="vid_101",
        clip_id=clip_id,
        virality_score=7.0,
        detailed_scores={"hook_strength": 7}
    )
    analytics_db.update_creator_action(clip_id=clip_id, published=True)
    
    response_sync = client.post("/api/youtube/sync")
    assert response_sync.status_code == 200
    sync_data = response_sync.json()
    assert sync_data["status"] == "success"
    assert sync_data["synced_count"] >= 1


# --- OAuth CSRF State Validation Tests ---

def test_oauth_csrf_valid_state():
    """Full round-trip: /auth stores state, /callback validates it successfully."""
    from youtube_service import _oauth_state_store, _oauth_state_lock
    
    # Hit /auth to generate and store a state token
    response = client.get("/api/youtube/auth", follow_redirects=False)
    assert response.status_code == 307  # RedirectResponse
    
    redirect_url = response.headers["location"]
    # Extract state and code from the mock redirect URL
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    
    assert "state" in params, "State parameter must be present in auth redirect URL"
    assert "code" in params, "Code parameter must be present in mock auth redirect URL"
    
    state = params["state"][0]
    code = params["code"][0]
    
    # Verify state was persisted in the store
    with _oauth_state_lock:
        assert state in _oauth_state_store, "State must be stored server-side after /auth"
    
    # Now call /callback with the correct state — should succeed
    callback_response = client.get(
        f"/api/youtube/callback?code={code}&state={state}",
        follow_redirects=False
    )
    # Successful callback redirects to /?tab=youtube-tab
    assert callback_response.status_code == 307
    assert "tab=youtube-tab" in callback_response.headers["location"]
    
    # Verify state was consumed (removed from store)
    with _oauth_state_lock:
        assert state not in _oauth_state_store, "State must be consumed after successful validation"


def test_oauth_csrf_invalid_state():
    """Callback with a forged/invalid state token must be rejected with HTTP 400."""
    response = client.get(
        "/api/youtube/callback?code=mock_code_123&state=forged_attacker_state_token",
        follow_redirects=False
    )
    assert response.status_code == 400
    assert "Invalid or expired" in response.json()["detail"]


def test_oauth_csrf_missing_state():
    """Callback without a state parameter must be rejected with HTTP 400."""
    response = client.get(
        "/api/youtube/callback?code=mock_code_123",
        follow_redirects=False
    )
    assert response.status_code == 400
    assert "Missing OAuth state parameter" in response.json()["detail"]


def test_oauth_csrf_replay_attack():
    """A state token must be single-use. Replaying a consumed state must fail."""
    from youtube_service import _oauth_state_store, _oauth_state_lock
    
    # Generate a state via /auth
    response = client.get("/api/youtube/auth", follow_redirects=False)
    assert response.status_code == 307
    
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(response.headers["location"])
    params = parse_qs(parsed.query)
    state = params["state"][0]
    code = params["code"][0]
    
    # First use — should succeed
    first_callback = client.get(
        f"/api/youtube/callback?code={code}&state={state}",
        follow_redirects=False
    )
    assert first_callback.status_code == 307
    assert "tab=youtube-tab" in first_callback.headers["location"]
    
    # Replay — same state again — must be rejected
    replay_callback = client.get(
        f"/api/youtube/callback?code={code}&state={state}",
        follow_redirects=False
    )
    assert replay_callback.status_code == 400
    assert "Invalid or expired" in replay_callback.json()["detail"]
    
    # Verify store is still clean
    with _oauth_state_lock:
        assert state not in _oauth_state_store


# --- Production Hardening Tests ---

def test_mock_oauth_blocked_in_production():
    """Mock OAuth mode must raise RuntimeError when APP_ENV=production."""
    with patch.dict(os.environ, {"APP_ENV": "production", "YOUTUBE_CLIENT_ID": "", "YOUTUBE_CLIENT_SECRET": ""}):
        from youtube_service import is_mock_mode
        with pytest.raises(RuntimeError, match="Mock OAuth mode is forbidden in production"):
            is_mock_mode()


def test_encryption_key_required_in_production():
    """Missing ENCRYPTION_KEY must raise RuntimeError when APP_ENV=production."""
    with patch.dict(os.environ, {"APP_ENV": "production", "ENCRYPTION_KEY": ""}):
        from youtube_service import _get_encryption_key
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY must be pre-set in production"):
            _get_encryption_key()


def test_encryption_key_no_disk_write_in_beta(tmp_path):
    """In beta mode, ENCRYPTION_KEY must NOT be auto-written to .env."""
    # Create a temporary .env file
    fake_env = tmp_path / ".env"
    fake_env.write_text("# test env\n")
    original_content = fake_env.read_text()

    with patch.dict(os.environ, {"APP_ENV": "beta", "ENCRYPTION_KEY": ""}):
        from youtube_service import _get_encryption_key
        # Patch the env_path calculation to point to our tmp file
        with patch("youtube_service.os.path.abspath", return_value=str(fake_env)):
            key = _get_encryption_key()
            assert key  # Should generate a key
            # File must NOT have been modified
            assert fake_env.read_text() == original_content


def test_redirect_uri_rejected_for_unlisted_origin():
    """Callback from a non-allowed origin must be rejected with HTTP 400."""
    # Set ALLOWED_ORIGINS to something that excludes the testserver
    with patch.dict(os.environ, {"ALLOWED_ORIGINS": "https://production.example.com", "YOUTUBE_REDIRECT_URI": ""}):
        # Force config to re-read the env var by reimporting
        from config import settings
        # Call /auth — the testserver origin (http://testserver) should fail validation
        response = client.get("/api/youtube/auth", follow_redirects=False)
        assert response.status_code == 400
        assert "not in the allowed origins list" in response.json()["detail"]
