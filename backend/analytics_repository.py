import os
import sqlite3
import json
import time
from abc import ABC, abstractmethod
from typing import Optional

class AnalyticsRepository(ABC):
    @abstractmethod
    def init_db(self):
        pass

    @abstractmethod
    def get_clips_by_video_id(self, video_id: str) -> list[dict]:
        pass

    @abstractmethod
    def get_clip_by_id(self, clip_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    def save_clip_metadata(self, video_id: str, clip_id: str, virality_score: float, detailed_scores: dict, experiment_id: str = None, variant_id: str = None, scoring_version: str = None, prompt_version: str = None, weight_version: str = None, title: str = None, reason: str = None, shorts_title: str = None, shorts_description: str = None, shorts_tags: list = None, duration: float = None, subtitle_style: str = None, creator_preset: str = None, words_per_chunk: float = None, reading_speed: float = None, highlight_count: int = None, render_time_ms: int = None, ass_event_count: int = None, fallback_used: bool = None, subtitle_version: str = None, face_position: str = None, start_time: float = None, end_time: float = None, start_index: int = None, end_index: int = None, upload_package: dict = None, emotion: str = None, energy_level: int = None, music_description: str = None, volume_pct: int = None, music_source: str = None, has_music: bool = None):
        pass

    @abstractmethod
    def update_clip_analytics(self, clip_id: str, platform: str, views: int, likes: int, comments: int, shares: int, watch_time: float, retention: float, upload_date: str):
        pass

    @abstractmethod
    def submit_clip_feedback(self, clip_id: str, feedback: str):
        pass

    @abstractmethod
    def update_creator_action(self, clip_id: str, selected: bool = None, rejected: bool = None, published: bool = None):
        pass

    @abstractmethod
    def get_correlation_data(self) -> list[dict]:
        pass

    @abstractmethod
    def get_all_records(self) -> list[dict]:
        pass

    @abstractmethod
    def save_credentials(self, platform: str, access_token: str, refresh_token: str, token_expiry: float, channel_name: str = None, channel_id: str = None):
        pass

    @abstractmethod
    def get_credentials(self, platform: str) -> Optional[dict]:
        pass

    @abstractmethod
    def delete_credentials(self, platform: str):
        pass

    @abstractmethod
    def update_clip_youtube_info(self, clip_id: str, youtube_video_id: str, youtube_url: str):
        pass

    @abstractmethod
    def save_analytics_snapshot(self, clip_id: str, views: int, likes: int, comments: int, watch_time: float, retention: float, snapshot_time: float = None):
        pass

    @abstractmethod
    def get_analytics_snapshots(self, clip_id: str) -> list[dict]:
        pass

    @abstractmethod
    def save_transcript_metric(self, video_id: str, source: str, failures: list, fallback_used: bool, duration: float):
        pass

    @abstractmethod
    def get_transcript_metrics_summary(self) -> dict:
        pass

    @abstractmethod
    def save_creator_profile_state(self, profile_version: str, style_preferences: dict, virality_weights: dict):
        pass

    @abstractmethod
    def get_creator_profile_state(self, profile_version: str) -> Optional[dict]:
        pass

class SqliteAnalyticsRepository(AnalyticsRepository):
    def __init__(self, db_path: str = None):
        if db_path is None:
            from config import settings
            db_url = settings.DATABASE_URL
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
            else:
                db_path = "output/analytics.db"
        self.db_path = db_path
        # Ensure directories exist
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        return conn

    def init_db(self):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS clip_analytics (
                        video_id TEXT NOT NULL,
                        clip_id TEXT PRIMARY KEY,
                        virality_score REAL NOT NULL,
                        detailed_scores TEXT NOT NULL,
                        upload_date TEXT,
                        platform TEXT,
                        views INTEGER DEFAULT 0,
                        likes INTEGER DEFAULT 0,
                        comments INTEGER DEFAULT 0,
                        shares INTEGER DEFAULT 0,
                        watch_time REAL DEFAULT 0.0,
                        retention REAL DEFAULT 0.0,
                        feedback TEXT,
                        published INTEGER DEFAULT 0,
                        creator_selected INTEGER DEFAULT 0,
                        creator_rejected INTEGER DEFAULT 0,
                        experiment_id TEXT,
                        variant_id TEXT,
                        scoring_version TEXT,
                        prompt_version TEXT,
                        weight_version TEXT,
                        created_at REAL NOT NULL
                    )
                """)
                
                # New tables for Phase 11A YouTube Analytics Feedback Loop
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS creator_credentials (
                        platform TEXT PRIMARY KEY,
                        access_token TEXT NOT NULL,
                        refresh_token TEXT NOT NULL,
                        token_expiry REAL NOT NULL,
                        channel_name TEXT,
                        channel_id TEXT,
                        updated_at REAL NOT NULL
                    )
                """)
                cursor.execute("PRAGMA table_info(creator_credentials)")
                cred_columns = [row[1] for row in cursor.fetchall()]
                if "channel_id" not in cred_columns:
                    cursor.execute("ALTER TABLE creator_credentials ADD COLUMN channel_id TEXT")
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS clip_analytics_snapshots (
                        clip_id TEXT NOT NULL,
                        snapshot_time REAL NOT NULL,
                        views INTEGER DEFAULT 0,
                        likes INTEGER DEFAULT 0,
                        comments INTEGER DEFAULT 0,
                        watch_time REAL DEFAULT 0.0,
                        retention REAL DEFAULT 0.0,
                        PRIMARY KEY (clip_id, snapshot_time)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS transcript_metrics (
                        video_id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        failures TEXT,
                        fallback_used INTEGER DEFAULT 0,
                        duration REAL DEFAULT 0.0,
                        created_at REAL NOT NULL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS creator_profile_state (
                        profile_version TEXT PRIMARY KEY,
                        style_preferences TEXT NOT NULL,
                        virality_weights TEXT NOT NULL,
                        last_updated REAL NOT NULL
                    )
                """)

                # Creator Brain Profile Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS creator_brain (
                        brain_id TEXT PRIMARY KEY,
                        creator_profile TEXT NOT NULL,
                        audience_profile TEXT NOT NULL,
                        goals TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """)

                # Styles and Editing Preferences Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS creator_preferences (
                        pref_id TEXT PRIMARY KEY,
                        style_prefs TEXT NOT NULL,
                        editing_prefs TEXT NOT NULL,
                        music_prefs TEXT NOT NULL,
                        publishing_schedule TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """)

                # Short & Long-Term Memory Logs
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS creator_memory (
                        memory_id TEXT PRIMARY KEY,
                        category TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)

                # Lessons Learned and Anti-Patterns Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS creator_lessons (
                        lesson_id TEXT PRIMARY KEY,
                        type TEXT NOT NULL,
                        concept TEXT NOT NULL,
                        description TEXT NOT NULL,
                        source_clip_id TEXT,
                        created_at REAL NOT NULL
                    )
                """)

                # Virality Predictions Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS creator_predictions (
                        clip_id TEXT PRIMARY KEY,
                        predicted_score REAL NOT NULL,
                        detailed_predictions TEXT NOT NULL,
                        target_audience TEXT NOT NULL,
                        reasoning TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)

                # Reflection logs Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS creator_reflections (
                        reflection_id TEXT PRIMARY KEY,
                        clip_id TEXT NOT NULL,
                        views_diff INTEGER NOT NULL,
                        retention_diff REAL NOT NULL,
                        evaluation TEXT NOT NULL,
                        weight_adjustments TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        FOREIGN KEY (clip_id) REFERENCES creator_predictions(clip_id)
                    )
                """)

                # Indexed Patterns Tables
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS successful_patterns (
                        pattern_id TEXT PRIMARY KEY,
                        pattern_type TEXT NOT NULL,
                        text_content TEXT NOT NULL,
                        success_metrics TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS failed_patterns (
                        pattern_id TEXT PRIMARY KEY,
                        pattern_type TEXT NOT NULL,
                        text_content TEXT NOT NULL,
                        fail_reason TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)
                
                # Dynamic schema migration for older databases
                cursor.execute("PRAGMA table_info(clip_analytics)")
                columns = [row[1] for row in cursor.fetchall()]
                new_cols = {
                    "experiment_id": "TEXT",
                    "variant_id": "TEXT",
                    "scoring_version": "TEXT",
                    "prompt_version": "TEXT",
                    "weight_version": "TEXT",
                    "title": "TEXT",
                    "reason": "TEXT",
                    "shorts_title": "TEXT",
                    "shorts_description": "TEXT",
                    "shorts_tags": "TEXT",
                    "duration": "REAL",
                    "subtitle_style": "TEXT",
                    "creator_preset": "TEXT",
                    "words_per_chunk": "REAL",
                    "reading_speed": "REAL",
                    "highlight_count": "INTEGER",
                    "render_time_ms": "INTEGER",
                    "ass_event_count": "INTEGER",
                    "fallback_used": "INTEGER",
                    "subtitle_version": "TEXT",
                    "face_position": "TEXT",
                    "start_time": "REAL",
                    "end_time": "REAL",
                    "start_index": "INTEGER",
                    "end_index": "INTEGER",
                    "upload_package": "TEXT",
                    "emotion": "TEXT",
                    "energy_level": "INTEGER",
                    "music_description": "TEXT",
                    "volume_pct": "INTEGER",
                    "music_source": "TEXT",
                    "has_music": "INTEGER",
                    "youtube_video_id": "TEXT",
                    "youtube_url": "TEXT"
                }
                for col, col_type in new_cols.items():
                    if col not in columns:
                        cursor.execute(f"ALTER TABLE clip_analytics ADD COLUMN {col} {col_type}")
        finally:
            conn.close()

    def save_clip_metadata(self, video_id: str, clip_id: str, virality_score: float, detailed_scores: dict, experiment_id: str = None, variant_id: str = None, scoring_version: str = None, prompt_version: str = None, weight_version: str = None, title: str = None, reason: str = None, shorts_title: str = None, shorts_description: str = None, shorts_tags: list = None, duration: float = None, subtitle_style: str = None, creator_preset: str = None, words_per_chunk: float = None, reading_speed: float = None, highlight_count: int = None, render_time_ms: int = None, ass_event_count: int = None, fallback_used: bool = None, subtitle_version: str = None, face_position: str = None, start_time: float = None, end_time: float = None, start_index: int = None, end_index: int = None, upload_package: dict = None, emotion: str = None, energy_level: int = None, music_description: str = None, volume_pct: int = None, music_source: str = None, has_music: bool = None):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                tags_str = json.dumps(shorts_tags) if shorts_tags is not None else None
                
                # Build query dynamically to insert only available fields or standard insert query with all fields
                cursor.execute("""
                    INSERT OR REPLACE INTO clip_analytics (
                        video_id, clip_id, virality_score, detailed_scores,
                        experiment_id, variant_id, scoring_version, prompt_version, weight_version,
                        title, reason, shorts_title, shorts_description, shorts_tags, duration,
                        subtitle_style, creator_preset, words_per_chunk, reading_speed, highlight_count,
                        render_time_ms, ass_event_count, fallback_used, subtitle_version, face_position,
                        start_time, end_time, start_index, end_index,
                        upload_package,
                        emotion, energy_level, music_description, volume_pct, music_source, has_music,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    video_id, clip_id, virality_score, json.dumps(detailed_scores),
                    experiment_id, variant_id, scoring_version, prompt_version, weight_version,
                    title, reason, shorts_title, shorts_description, tags_str, duration,
                    subtitle_style, creator_preset, words_per_chunk, reading_speed, highlight_count,
                    render_time_ms, ass_event_count, (1 if fallback_used else 0) if fallback_used is not None else None, subtitle_version, face_position,
                    start_time, end_time, start_index, end_index,
                    json.dumps(upload_package) if upload_package is not None else None,
                    emotion, energy_level, music_description, volume_pct, music_source, (1 if has_music else 0) if has_music is not None else 0,
                    time.time()
                ))
        finally:
            conn.close()

    def update_clip_analytics(self, clip_id: str, platform: str, views: int, likes: int, comments: int, shares: int, watch_time: float, retention: float, upload_date: str):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE clip_analytics
                    SET platform = ?, views = ?, likes = ?, comments = ?, shares = ?, watch_time = ?, retention = ?, upload_date = ?
                    WHERE clip_id = ?
                """, (platform, views, likes, comments, shares, watch_time, retention, upload_date, clip_id))
        finally:
            conn.close()

    def submit_clip_feedback(self, clip_id: str, feedback: str):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE clip_analytics
                    SET feedback = ?
                    WHERE clip_id = ?
                """, (feedback, clip_id))
        finally:
            conn.close()

    def update_creator_action(self, clip_id: str, selected: bool = None, rejected: bool = None, published: bool = None):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                updates = []
                params = []
                if selected is not None:
                    updates.append("creator_selected = ?")
                    params.append(1 if selected else 0)
                if rejected is not None:
                    updates.append("creator_rejected = ?")
                    params.append(1 if rejected else 0)
                if published is not None:
                    updates.append("published = ?")
                    params.append(1 if published else 0)
                    
                if updates:
                    params.append(clip_id)
                    query = f"UPDATE clip_analytics SET {', '.join(updates)} WHERE clip_id = ?"
                    cursor.execute(query, params)
        finally:
            conn.close()

    def get_correlation_data(self) -> list[dict]:
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT virality_score, detailed_scores, views, retention, shares
                FROM clip_analytics
                WHERE views > 0 OR retention > 0.0 OR shares > 0
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_all_records(self) -> list[dict]:
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clip_analytics")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def save_credentials(self, platform: str, access_token: str, refresh_token: str, token_expiry: float, channel_name: str = None, channel_id: str = None):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO creator_credentials (
                        platform, access_token, refresh_token, token_expiry, channel_name, channel_id, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (platform, access_token, refresh_token, token_expiry, channel_name, channel_id, time.time()))
        finally:
            conn.close()

    def get_credentials(self, platform: str) -> Optional[dict]:
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT platform, access_token, refresh_token, token_expiry, channel_name, channel_id, updated_at
                FROM creator_credentials
                WHERE platform = ?
            """, (platform,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_credentials(self, platform: str):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM creator_credentials WHERE platform = ?", (platform,))
        finally:
            conn.close()

    def update_clip_youtube_info(self, clip_id: str, youtube_video_id: str, youtube_url: str):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE clip_analytics
                    SET youtube_video_id = ?, youtube_url = ?
                    WHERE clip_id = ?
                """, (youtube_video_id, youtube_url, clip_id))
        finally:
            conn.close()

    def save_analytics_snapshot(self, clip_id: str, views: int, likes: int, comments: int, watch_time: float, retention: float, snapshot_time: float = None):
        if snapshot_time is None:
            snapshot_time = time.time()
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO clip_analytics_snapshots (
                        clip_id, snapshot_time, views, likes, comments, watch_time, retention
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (clip_id, snapshot_time, views, likes, comments, watch_time, retention))
        finally:
            conn.close()

    def get_analytics_snapshots(self, clip_id: str) -> list[dict]:
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT clip_id, snapshot_time, views, likes, comments, watch_time, retention
                FROM clip_analytics_snapshots
                WHERE clip_id = ?
                ORDER BY snapshot_time ASC
            """, (clip_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def save_transcript_metric(self, video_id: str, source: str, failures: list, fallback_used: bool, duration: float):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                failures_str = json.dumps(failures) if failures else "[]"
                cursor.execute("""
                    INSERT OR REPLACE INTO transcript_metrics (
                        video_id, source, failures, fallback_used, duration, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (video_id, source, failures_str, 1 if fallback_used else 0, duration, time.time()))
        finally:
            conn.close()

    def get_transcript_metrics_summary(self) -> dict:
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT source, COUNT(*) as count, AVG(duration) as avg_duration FROM transcript_metrics GROUP BY source")
            rows = cursor.fetchall()
            
            source_breakdown = {}
            total_runs = 0
            total_duration = 0.0
            
            for row in rows:
                src = row["source"]
                cnt = row["count"]
                avg_dur = row["avg_duration"] or 0.0
                
                source_breakdown[src] = cnt
                total_runs += cnt
                total_duration += (avg_dur * cnt)
                
            cursor.execute("SELECT COUNT(*) FROM transcript_metrics WHERE fallback_used = 1")
            total_fallbacks = cursor.fetchone()[0]
            
            fallback_rate = (total_fallbacks / total_runs * 100.0) if total_runs > 0 else 0.0
            avg_transcription_time = (total_duration / total_runs) if total_runs > 0 else 0.0
            
            return {
                "total_runs": total_runs,
                "fallback_used_count": total_fallbacks,
                "fallback_usage_percent": round(fallback_rate, 2),
                "average_transcription_time": round(avg_transcription_time, 2),
                "source_breakdown": source_breakdown
            }
        finally:
            conn.close()

    def get_last_sync_time(self) -> float:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(snapshot_time) FROM clip_analytics_snapshots")
            val = cursor.fetchone()[0]
            return val if val else 0.0
        finally:
            conn.close()

    def get_clips_by_video_id(self, video_id: str) -> list[dict]:
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM clip_analytics 
                WHERE video_id = ?
                ORDER BY virality_score DESC
            """, (video_id,))
            rows = cursor.fetchall()
            
            clips = []
            for row in rows:
                c = dict(row)
                try:
                    c["detailed_scores"] = json.loads(c["detailed_scores"])
                except Exception:
                    c["detailed_scores"] = {}
                try:
                    c["shorts_tags"] = json.loads(c["shorts_tags"]) if c["shorts_tags"] else []
                except Exception:
                    c["shorts_tags"] = []
                try:
                    c["upload_package"] = json.loads(c["upload_package"]) if c.get("upload_package") else None
                except Exception:
                    c["upload_package"] = None
                clips.append(c)
            return clips
        finally:
            conn.close()

    def get_clip_by_id(self, clip_id: str) -> Optional[dict]:
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM clip_analytics
                WHERE clip_id = ?
            """, (clip_id,))
            row = cursor.fetchone()
            if not row:
                return None
            c = dict(row)
            try:
                c["detailed_scores"] = json.loads(c["detailed_scores"])
            except Exception:
                c["detailed_scores"] = {}
            try:
                c["shorts_tags"] = json.loads(c["shorts_tags"]) if c["shorts_tags"] else []
            except Exception:
                c["shorts_tags"] = []
            try:
                c["upload_package"] = json.loads(c["upload_package"]) if c.get("upload_package") else None
            except Exception:
                c["upload_package"] = None
            return c
        finally:
            conn.close()

    def save_creator_profile_state(self, profile_version: str, style_preferences: dict, virality_weights: dict):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO creator_profile_state (profile_version, style_preferences, virality_weights, last_updated)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(profile_version) DO UPDATE SET
                        style_preferences = excluded.style_preferences,
                        virality_weights = excluded.virality_weights,
                        last_updated = excluded.last_updated
                """, (
                    profile_version,
                    json.dumps(style_preferences),
                    json.dumps(virality_weights),
                    time.time()
                ))
        finally:
            conn.close()

    def get_creator_profile_state(self, profile_version: str) -> Optional[dict]:
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM creator_profile_state
                WHERE profile_version = ?
            """, (profile_version,))
            row = cursor.fetchone()
            if not row:
                return None
            p = dict(row)
            try:
                p["style_preferences"] = json.loads(p["style_preferences"])
            except Exception:
                p["style_preferences"] = {}
            try:
                p["virality_weights"] = json.loads(p["virality_weights"])
            except Exception:
                p["virality_weights"] = {}
            return p
        finally:
            conn.close()

# Global database instance
db = SqliteAnalyticsRepository()
