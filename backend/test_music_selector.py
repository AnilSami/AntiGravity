"""
test_music_selector.py — Phase 24: AI Emotion-Matched Background Music

Tests:
  1. Mock mode returns correct defaults (no API call)
  2. Emotion field sanitization and clamping
  3. ElevenLabs API failure falls back to Freesound → returns None (no crash)
  4. mix_music_into_clip handles missing music file gracefully
  5. analyze_clip_emotion handles LLM failure gracefully
  6. fetch_elevenlabs_music skips cached file check
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(__file__))


class TestAnalyzeClipEmotion(unittest.TestCase):
    """Tests for analyze_clip_emotion()"""

    def test_mock_mode_returns_default_emotion(self):
        """Mock API key → returns deterministic defaults without any API call."""
        from music_selector import analyze_clip_emotion
        result = analyze_clip_emotion(
            clip_text="This is how you build a startup.",
            hook="Nobody talks about this.",
            api_key="mock-key-123"
        )
        self.assertIn("emotion", result)
        self.assertIn("energy_level", result)
        self.assertIn("music_description", result)
        self.assertIn("volume_pct", result)
        self.assertIn("fade_in_secs", result)
        self.assertIn("fade_out_secs", result)
        # Default values
        self.assertEqual(result["emotion"], "motivational")
        self.assertEqual(result["energy_level"], 6)
        self.assertEqual(result["volume_pct"], 8)  # Phase 26: default lowered from 15

    def test_emotion_fields_are_in_spec(self):
        """All returned fields must be within spec ranges."""
        from music_selector import analyze_clip_emotion, VALID_EMOTIONS
        result = analyze_clip_emotion(
            clip_text="Sample text",
            hook="Sample hook",
            api_key="mock"
        )
        self.assertIn(result["emotion"], VALID_EMOTIONS)
        self.assertGreaterEqual(result["energy_level"], 1)
        self.assertLessEqual(result["energy_level"], 10)
        self.assertGreaterEqual(result["volume_pct"], 6)   # Phase 26: range is [6, 10]
        self.assertLessEqual(result["volume_pct"], 10)
        self.assertGreaterEqual(result["fade_in_secs"], 0.5)
        self.assertLessEqual(result["fade_in_secs"], 2.0)
        self.assertGreaterEqual(result["fade_out_secs"], 1.0)
        self.assertLessEqual(result["fade_out_secs"], 3.0)

    def test_llm_failure_returns_safe_defaults(self):
        """If LLM call raises, returns safe default emotion dict without crashing."""
        from music_selector import analyze_clip_emotion
        with patch("music_selector.LLMResilienceManager") as mock_llm_cls:
            mock_instance = MagicMock()
            mock_instance.call.side_effect = Exception("Connection timeout")
            mock_llm_cls.return_value = mock_instance

            result = analyze_clip_emotion(
                clip_text="Test",
                hook="Test hook",
                api_key="real-looking-key-abc123"
            )

        self.assertIn("emotion", result)
        self.assertEqual(result["emotion"], "motivational")  # safe default

    def test_invalid_emotion_replaced_with_default(self):
        """If LLM returns an emotion not in VALID_EMOTIONS, uses default."""
        from music_selector import analyze_clip_emotion
        with patch("music_selector.LLMResilienceManager") as mock_llm_cls, \
             patch("music_selector._extract_json_from_response") as mock_extract:

            mock_extract.return_value = json.dumps({
                "emotion": "chaotic",       # invalid
                "energy_level": 7,
                "music_description": "test music",
                "volume_pct": 18,
                "fade_in_secs": 1.0,
                "fade_out_secs": 2.0
            })
            mock_instance = MagicMock()
            mock_instance.call.return_value = "{}"
            mock_llm_cls.return_value = mock_instance

            result = analyze_clip_emotion(
                clip_text="Test",
                hook="Hook",
                api_key="real-key"
            )

        # "chaotic" is not in VALID_EMOTIONS, so default must be used
        self.assertEqual(result["emotion"], "motivational")
        # But valid fields like energy_level should come through
        self.assertEqual(result["energy_level"], 7)


class TestLocalMusicLibrary(unittest.TestCase):
    """Tests for local music library track selection and caching."""

    def test_music_disabled_returns_none(self):
        """If MUSIC_ENABLED=false, should return None and save metadata."""
        from music_selector import fetch_elevenlabs_music
        with patch.dict(os.environ, {"MUSIC_ENABLED": "false"}):
            result = fetch_elevenlabs_music(
                music_description="test",
                duration_seconds=30.0,
                clip_id="test_disabled"
            )
        self.assertIsNone(result)
        
        # Verify metadata file is written with has_music=False
        meta_path = "output/cache/music_metadata_test_disabled.json"
        self.assertTrue(os.path.exists(meta_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertFalse(meta["has_music"])
        self.assertEqual(meta["music_source"], "none")

    def test_empty_library_returns_none_gracefully(self):
        """If library directory is empty, should return None and log warning."""
        from music_selector import fetch_elevenlabs_music
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"MUSIC_LIBRARY_PATH": tmpdir, "MUSIC_ENABLED": "true"}):
                result = fetch_elevenlabs_music(
                    music_description="test",
                    duration_seconds=30.0,
                    clip_id="test_empty"
                )
        self.assertIsNone(result)

    def test_fallback_to_root(self):
        """If category folder is empty, fallback to a file in root of library path."""
        from music_selector import fetch_elevenlabs_music
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create category dir (empty)
            os.makedirs(os.path.join(tmpdir, "inspirational"), exist_ok=True)
            # Create a file in root
            root_track = os.path.join(tmpdir, "root_track.mp3")
            with open(root_track, "wb") as f:
                f.write(b"X" * 1024)
                
            with patch.dict(os.environ, {"MUSIC_LIBRARY_PATH": tmpdir, "MUSIC_ENABLED": "true"}):
                result = fetch_elevenlabs_music(
                    music_description="test",
                    duration_seconds=30.0,
                    clip_id="test_fallback_root",
                    emotion="inspirational"
                )
        self.assertEqual(result, root_track)
        
        # Verify metadata
        meta_path = "output/cache/music_metadata_test_fallback_root.json"
        self.assertTrue(os.path.exists(meta_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertTrue(meta["has_music"])
        self.assertEqual(meta["music_source"], "local_library")
        self.assertEqual(meta["music_category"], "inspirational")
        self.assertEqual(meta["music_file"].replace("\\", "/"), root_track.replace("\\", "/"))

    def test_fallback_to_recursive(self):
        """If category and root empty, recursively find any audio file."""
        from music_selector import fetch_elevenlabs_music
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested subfolder
            nested_dir = os.path.join(tmpdir, "some", "nested", "folder")
            os.makedirs(nested_dir, exist_ok=True)
            nested_track = os.path.join(nested_dir, "nested_track.wav")
            with open(nested_track, "wb") as f:
                f.write(b"X" * 1024)
                
            with patch.dict(os.environ, {"MUSIC_LIBRARY_PATH": tmpdir, "MUSIC_ENABLED": "true"}):
                result = fetch_elevenlabs_music(
                    music_description="test",
                    duration_seconds=30.0,
                    clip_id="test_recursive",
                    emotion="calm"
                )
        self.assertEqual(result, nested_track)

    def test_random_vs_sorted_selection(self):
        """When RANDOMIZE_TRACKS=false, selection is deterministic (sorted first file)."""
        from music_selector import fetch_elevenlabs_music
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "calm"), exist_ok=True)
            track_a = os.path.join(tmpdir, "calm", "track_a.mp3")
            track_b = os.path.join(tmpdir, "calm", "track_b.mp3")
            with open(track_a, "wb") as f: f.write(b"X")
            with open(track_b, "wb") as f: f.write(b"X")
            
            with patch.dict(os.environ, {"MUSIC_LIBRARY_PATH": tmpdir, "MUSIC_ENABLED": "true", "RANDOMIZE_TRACKS": "false"}):
                result1 = fetch_elevenlabs_music("test", 30.0, "test_select_1", emotion="calm")
                from music_selector import _RECENT_TRACK_QUEUE
                _RECENT_TRACK_QUEUE.clear()
                result2 = fetch_elevenlabs_music("test", 30.0, "test_select_2", emotion="calm")
                
        self.assertEqual(result1, track_a)
        self.assertEqual(result2, track_a)

    def test_fifo_recently_used_tracks(self):
        """Tracks selected recently are avoided if others exist."""
        from music_selector import fetch_elevenlabs_music
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "calm"), exist_ok=True)
            track_a = os.path.join(tmpdir, "calm", "track_a.mp3")
            track_b = os.path.join(tmpdir, "calm", "track_b.mp3")
            with open(track_a, "wb") as f: f.write(b"X")
            with open(track_b, "wb") as f: f.write(b"X")
            
            from music_selector import _RECENT_TRACK_QUEUE
            _RECENT_TRACK_QUEUE.clear()
            
            with patch.dict(os.environ, {"MUSIC_LIBRARY_PATH": tmpdir, "MUSIC_ENABLED": "true", "RANDOMIZE_TRACKS": "false"}):
                result1 = fetch_elevenlabs_music("test", 30.0, "test_fifo_1", emotion="calm")
                result2 = fetch_elevenlabs_music("test", 30.0, "test_fifo_2", emotion="calm")
                
        self.assertEqual(result1, track_a)
        self.assertEqual(result2, track_b)

    def test_fallback_to_default_folder(self):
        """If category folder is empty/missing, it falls back to 'default' folder."""
        from music_selector import fetch_elevenlabs_music
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create default dir with track
            os.makedirs(os.path.join(tmpdir, "default"), exist_ok=True)
            default_track = os.path.join(tmpdir, "default", "fallback.mp3")
            with open(default_track, "wb") as f:
                f.write(b"X")
                
            with patch.dict(os.environ, {"MUSIC_LIBRARY_PATH": tmpdir, "MUSIC_ENABLED": "true"}):
                result = fetch_elevenlabs_music(
                    music_description="test",
                    duration_seconds=30.0,
                    clip_id="test_fallback_default",
                    emotion="uplifting"  # uplifting is empty, should check default/
                )
        self.assertEqual(result, default_track)

    def test_license_info_extraction(self):
        """Reads license details from companion .json file."""
        from music_selector import fetch_elevenlabs_music
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "calm"), exist_ok=True)
            track_path = os.path.join(tmpdir, "calm", "premium_track.wav")
            json_path = os.path.join(tmpdir, "calm", "premium_track.json")
            with open(track_path, "wb") as f:
                f.write(b"X")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({"license": "Creative Commons 4.0", "license_id": "CC-BY-4.0-XYZ"}, f)
                
            with patch.dict(os.environ, {"MUSIC_LIBRARY_PATH": tmpdir, "MUSIC_ENABLED": "true"}):
                fetch_elevenlabs_music("test", 30.0, "test_license", emotion="calm")
                
        # Check metadata
        meta_path = "output/cache/music_metadata_test_license.json"
        self.assertTrue(os.path.exists(meta_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["license"], "Creative Commons 4.0")
        self.assertEqual(meta["license_id"], "CC-BY-4.0-XYZ")

    def test_additional_formats(self):
        """Supports various formats: mp3, wav, m4a, ogg, flac."""
        from music_selector import fetch_elevenlabs_music
        formats = [".mp3", ".wav", ".m4a", ".ogg", ".flac"]
        for fmt in formats:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.makedirs(os.path.join(tmpdir, "calm"), exist_ok=True)
                track_path = os.path.join(tmpdir, "calm", f"track{fmt}")
                with open(track_path, "wb") as f:
                    f.write(b"X")
                    
                with patch.dict(os.environ, {"MUSIC_LIBRARY_PATH": tmpdir, "MUSIC_ENABLED": "true"}):
                    result = fetch_elevenlabs_music("test", 30.0, f"test_fmt_{fmt[1:]}", emotion="calm")
                self.assertEqual(result, track_path)


class TestMixMusicIntoClip(unittest.TestCase):
    """Tests for mix_music_into_clip()"""

    def test_missing_music_file_returns_original_clip(self):
        """If music file doesn't exist, original clip path is returned without crashing."""
        from music_selector import mix_music_into_clip
        result = mix_music_into_clip(
            clip_path="/nonexistent/clip.mp4",
            music_path="/nonexistent/music.mp3",
            volume_pct=15,
            fade_in_secs=1.0,
            fade_out_secs=2.0,
            duration=35.0,
            clip_id="test_no_music"
        )
        # Should return original clip path on failure
        self.assertEqual(result, "/nonexistent/clip.mp4")

    def test_ffmpeg_failure_returns_original_clip(self):
        """If FFmpeg exits non-zero, original clip path is returned."""
        from music_selector import mix_music_into_clip
        import subprocess

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: codec not found"

        with patch("subprocess.run", return_value=mock_result):
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as clip_f:
                clip_path = clip_f.name
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as music_f:
                music_path = music_f.name
            try:
                result = mix_music_into_clip(
                    clip_path=clip_path,
                    music_path=music_path,
                    volume_pct=20,
                    fade_in_secs=1.0,
                    fade_out_secs=2.0,
                    duration=30.0,
                    clip_id="test_ffmpeg_fail"
                )
                self.assertEqual(result, clip_path)
            finally:
                os.unlink(clip_path)
                os.unlink(music_path)

    def test_ffmpeg_timeout_returns_original_clip(self):
        """FFmpeg timeout should not crash; returns original clip path."""
        from music_selector import mix_music_into_clip
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120)):
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as clip_f:
                clip_path = clip_f.name
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as music_f:
                music_path = music_f.name
            try:
                result = mix_music_into_clip(
                    clip_path=clip_path,
                    music_path=music_path,
                    volume_pct=15,
                    fade_in_secs=1.0,
                    fade_out_secs=2.0,
                    duration=40.0,
                    clip_id="test_timeout"
                )
                self.assertEqual(result, clip_path)
            finally:
                os.unlink(clip_path)
                os.unlink(music_path)


class TestClipInfoMusicFields(unittest.TestCase):
    """Tests that ClipInfo model accepts new music fields."""

    def test_clipinfo_accepts_music_fields(self):
        """ClipInfo can be instantiated with all Phase 24 music fields."""
        from job_manager import ClipInfo
        clip = ClipInfo(
            id="abc12345",
            title="Test Clip",
            reason="Interesting moment",
            start_time=10.0,
            end_time=50.0,
            duration=40.0,
            filename="clip_abc12345_with_music.mp4",
            shorts_title="Test Short",
            shorts_description="Test description",
            shorts_tags=["test", "shorts"],
            virality_score=7.5,
            emotion="motivational",
            energy_level=7,
            music_description="driving electronic beat",
            volume_pct=20,
            music_source="local_library",
            has_music=True,
            music_category="inspirational",
            music_file="assets/music/inspirational/song1.mp3",
            license="Pixabay License",
            license_id="12345"
        )
        self.assertEqual(clip.emotion, "motivational")
        self.assertEqual(clip.energy_level, 7)
        self.assertEqual(clip.music_source, "local_library")
        self.assertEqual(clip.music_category, "inspirational")
        self.assertEqual(clip.music_file, "assets/music/inspirational/song1.mp3")
        self.assertEqual(clip.license, "Pixabay License")
        self.assertEqual(clip.license_id, "12345")
        self.assertTrue(clip.has_music)

    def test_clipinfo_default_no_music(self):
        """ClipInfo defaults have_music=False and None music fields."""
        from job_manager import ClipInfo
        clip = ClipInfo(
            id="xyz99999",
            title="Test",
            reason="Reason",
            start_time=0.0,
            end_time=30.0,
            duration=30.0,
            filename="clip_xyz99999.mp4",
            shorts_title="Short",
            shorts_description="Desc",
            shorts_tags=[]
        )
        self.assertFalse(clip.has_music)
        self.assertIsNone(clip.emotion)
        self.assertIsNone(clip.music_source)


class TestLikeOverlay(unittest.TestCase):
    """Tests for add_like_overlay()"""

    def test_missing_clip_returns_original_path(self):
        """If input clip doesn't exist, original path is returned without crashing."""
        from overlays import add_like_overlay
        result = add_like_overlay(
            clip_path="/nonexistent/clip.mp4",
            clip_id="test_no_clip",
            duration=30.0
        )
        self.assertEqual(result, "/nonexistent/clip.mp4")

    def test_ffmpeg_failure_returns_original_path(self):
        """If FFmpeg exits non-zero, original clip path is returned."""
        from overlays import add_like_overlay
        import subprocess

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: codec not found"

        with patch("subprocess.run", return_value=mock_result):
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as clip_f:
                clip_path = clip_f.name
            try:
                result = add_like_overlay(
                    clip_path=clip_path,
                    clip_id="test_fail",
                    duration=30.0
                )
                self.assertEqual(result, clip_path)
            finally:
                os.unlink(clip_path)

    def test_has_alpha_channel_detection(self):
        """Test that _has_alpha_channel accurately detects transparency flags."""
        from overlays import _has_alpha_channel
        import subprocess

        # Case 1: WebM with alpha tag
        mock_result = MagicMock()
        mock_result.stdout = "pix_fmt=yuv420p\nTAG:alpha_mode=1\n"
        with patch("subprocess.run", return_value=mock_result):
            self.assertTrue(_has_alpha_channel("dummy.webm"))

        # Case 2: Standard pixel format with alpha (yuva420p)
        mock_result.stdout = "pix_fmt=yuva420p\n"
        with patch("subprocess.run", return_value=mock_result):
            self.assertTrue(_has_alpha_channel("dummy.mov"))

        # Case 3: Palette transparent GIF format
        mock_result.stdout = "codec_name=gif\n"
        with patch("subprocess.run", return_value=mock_result):
            self.assertTrue(_has_alpha_channel("dummy.gif"))

        # Case 4: Standard MP4 without alpha
        mock_result.stdout = "pix_fmt=yuv420p\ncodec_name=h264\n"
        with patch("subprocess.run", return_value=mock_result):
            self.assertFalse(_has_alpha_channel("dummy.mp4"))

    def test_build_custom_asset_filter_colorkey(self):
        """Test _build_custom_asset_filter generates colorkey filter only if asset has no alpha."""
        from overlays import _build_custom_asset_filter
        
        # Test Case 1: Asset has alpha -> Scale only
        with patch("overlays._has_alpha_channel", return_value=True):
            filter_str = _build_custom_asset_filter("dummy.webm", [2.0], 1080)
            self.assertIn("scale=128:-2:flags=lanczos", filter_str)
            self.assertNotIn("colorkey", filter_str)

        # Test Case 2: Asset has no alpha -> Colorkey + Scale
        with patch("overlays._has_alpha_channel", return_value=False):
            with patch.dict("os.environ", {
                "LIKE_OVERLAY_KEY_COLOR": "white",
                "LIKE_OVERLAY_SIMILARITY": "0.03",
                "LIKE_OVERLAY_BLEND": "0.08"
            }):
                filter_str = _build_custom_asset_filter("dummy.mp4", [2.0], 1080)
                self.assertIn("colorkey=color=white:similarity=0.03:blend=0.08", filter_str)
                self.assertIn("scale=128:-2:flags=lanczos", filter_str)


if __name__ == "__main__":
    # Run all test cases
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestAnalyzeClipEmotion))
    suite.addTests(loader.loadTestsFromTestCase(TestLocalMusicLibrary))
    suite.addTests(loader.loadTestsFromTestCase(TestMixMusicIntoClip))
    suite.addTests(loader.loadTestsFromTestCase(TestClipInfoMusicFields))
    suite.addTests(loader.loadTestsFromTestCase(TestLikeOverlay))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
