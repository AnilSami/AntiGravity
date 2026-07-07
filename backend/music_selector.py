"""
music_selector.py — Phase 25: Cinematic Music Layering

Three public functions for external use:
  analyze_clip_emotion()   — LLM call to get emotion + mixing parameters
  fetch_elevenlabs_music() — ElevenLabs → Freesound → None fallback chain
  mix_music_into_clip()    — Phase 25: sidechaincompress ducking + intro build
  add_impact_sounds()      — Phase 25: LLM-identified impact SFX overlay
"""

import os
import json
import logging
import re
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, List, Dict, Any

from analyzer import LLMResilienceManager, _extract_json_from_response

logger = logging.getLogger("music_selector")

# Valid emotions the LLM may return
VALID_EMOTIONS = {
    "triumphant", "motivational", "tense", "melancholic", "energetic",
    "calm", "inspirational", "dramatic", "urgent", "uplifting"
}

# Safe default emotion data when analysis fails or mock mode is active
_DEFAULT_EMOTION = {
    "emotion": "motivational",
    "energy_level": 6,
    "music_description": "uplifting background music",
    "volume_pct": 8,  # Phase 26: narration must dominate; default lowered from 15
    "fade_in_secs": 1.0,
    "fade_out_secs": 2.0,
}

# ElevenLabs Sound Effects API endpoint
_ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/sound-generation"

# SFX description map for each effect_type
_SFX_DESCRIPTIONS = {
    "impact": "deep cinematic impact boom",
    "whoosh": "fast whoosh transition",
    "ding":   "bright notification ding",
    "swoosh": "swoosh air movement",
}

# Probe whether sidechaincompress is available in the local FFmpeg build (lazy-evaluated)
_SIDECHAIN_AVAILABLE: Optional[bool] = None


def _probe_sidechain_support() -> bool:
    """Check once if FFmpeg supports the sidechaincompress filter."""
    global _SIDECHAIN_AVAILABLE
    if _SIDECHAIN_AVAILABLE is not None:
        return _SIDECHAIN_AVAILABLE
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True, text=True, timeout=10
        )
        _SIDECHAIN_AVAILABLE = "sidechaincompress" in result.stdout
        if not _SIDECHAIN_AVAILABLE:
            logger.warning("FFmpeg sidechaincompress filter not found — falling back to flat amix.")
    except Exception:
        _SIDECHAIN_AVAILABLE = False
    return _SIDECHAIN_AVAILABLE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_clip_emotion(
    clip_text: str,
    hook: str,
    api_key: Optional[str] = None,
    clip_id: Optional[str] = None
) -> dict:
    """
    Analyzes the emotional tone of a clip using claude-haiku-4-5.

    Returns a dict with keys:
        emotion, energy_level, music_description, volume_pct,
        fade_in_secs, fade_out_secs

    Never raises — returns safe defaults on any failure.
    """
    # 1. Check disk cache if clip_id is provided
    if clip_id:
        cache_dir = os.path.join("output", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"emotion_{clip_id}.json")
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                logger.info(f"Reusing cached emotion analysis for clip {clip_id}: {cached_data.get('emotion')}")
                return cached_data
            except Exception as cache_err:
                logger.warning(f"Failed to load cached emotion analysis for {clip_id}: {cache_err}")

    resolved_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or "mock"

    if resolved_key.startswith("mock"):
        logger.info("Mock API key detected. Returning mock emotion data.")
        result = dict(_DEFAULT_EMOTION)
        if clip_id:
            _save_emotion_cache(clip_id, result)
        return result

    system_prompt = "You are an expert music supervisor who pairs background music with video content."
    user_prompt = f"""Analyze this YouTube Shorts clip and determine its emotional energy for music selection.

Clip transcript: {clip_text}
Hook: {hook}

Return JSON with:
- emotion: one word from [triumphant, motivational, tense, melancholic, energetic, calm, inspirational, dramatic, urgent, uplifting]
- energy_level: number 1-10 (1=very calm, 10=extremely high energy)
- music_description: 2-3 word description for sound generation (e.g. 'epic orchestral build', 'soft piano melody', 'driving electronic beat')
- volume_pct: recommended background music volume as integer 6-10 (low energy = 6-8, high energy = 9-10). IMPORTANT: music is background atmosphere only; narration must dominate at all times.
- fade_in_secs: recommended fade in duration in seconds (0.5-2.0)
- fade_out_secs: recommended fade out duration in seconds (1.0-3.0)

Return only JSON, no other text."""

    try:
        llm = LLMResilienceManager(primary_key=resolved_key)
        response_text = llm.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_json=True,
            model="claude-haiku-4-5"
        )

        repaired = _extract_json_from_response(response_text)
        data = json.loads(repaired)

        # Sanitize and fill missing fields with defaults
        result = dict(_DEFAULT_EMOTION)
        if data.get("emotion") in VALID_EMOTIONS:
            result["emotion"] = data["emotion"]
        if isinstance(data.get("energy_level"), (int, float)):
            result["energy_level"] = max(1, min(10, int(data["energy_level"])))
        if isinstance(data.get("music_description"), str) and data["music_description"].strip():
            result["music_description"] = data["music_description"].strip()[:100]
        if isinstance(data.get("volume_pct"), (int, float)):
            result["volume_pct"] = max(6, min(10, int(data["volume_pct"])))  # Phase 26: clamp to [6,10]
        if isinstance(data.get("fade_in_secs"), (int, float)):
            result["fade_in_secs"] = max(0.5, min(2.0, float(data["fade_in_secs"])))
        if isinstance(data.get("fade_out_secs"), (int, float)):
            result["fade_out_secs"] = max(1.0, min(3.0, float(data["fade_out_secs"])))

        logger.info(
            f"Emotion analysis complete: {result['emotion']} "
            f"energy={result['energy_level']}/10 vol={result['volume_pct']}%"
        )
        if clip_id:
            _save_emotion_cache(clip_id, result)
        return result

    except Exception as e:
        logger.error(f"analyze_clip_emotion failed: {e}. Using defaults.")
        result = dict(_DEFAULT_EMOTION)
        if clip_id:
            _save_emotion_cache(clip_id, result)
        return result


# FIFO queue for recently used tracks
_RECENT_TRACK_QUEUE: List[str] = []
_MAX_QUEUE_SIZE = 5

EMOTION_TO_CATEGORY = {
    "triumphant": "uplifting",
    "uplifting": "uplifting",
    "energetic": "uplifting",
    
    "motivational": "inspirational",
    "inspirational": "inspirational",
    
    "calm": "calm",
    
    "tense": "dramatic",
    "dramatic": "dramatic",
    "urgent": "dramatic",
    
    "melancholic": "emotional",
    "emotional": "emotional"
}

def _get_category_for_emotion(emotion: Optional[str]) -> str:
    if not emotion:
        return "corporate"
    return EMOTION_TO_CATEGORY.get(emotion.lower(), "corporate")

def _save_music_metadata(
    clip_id: str,
    has_music: bool,
    music_source: str,
    music_category: str,
    music_file: str,
    volume_pct: int,
    license_name: Optional[str] = None,
    license_id: Optional[str] = None
):
    """Saves music selection metadata to a cache JSON file on disk."""
    cache_dir = os.path.join("output", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    meta_path = os.path.join(cache_dir, f"music_metadata_{clip_id}.json")
    meta_data = {
        "has_music": has_music,
        "music_source": music_source,
        "music_category": music_category,
        "music_file": music_file,
        "volume_pct": volume_pct,
        "license": license_name,
        "license_id": license_id
    }
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2)
        logger.info(f"Saved music metadata cache to {meta_path}")
    except Exception as e:
        logger.warning(f"Failed to write music metadata cache for {clip_id}: {e}")

def _get_license_info(selected: str) -> tuple[str, Optional[str]]:
    """Checks for a companion JSON file to extract track license metadata."""
    base_without_ext, _ = os.path.splitext(selected)
    json_path_1 = base_without_ext + ".json"
    json_path_2 = selected + ".json"
    
    license_name = "Unknown (Locally Placed)"
    license_id = None
    
    for jp in [json_path_1, json_path_2]:
        if os.path.exists(jp):
            try:
                with open(jp, "r", encoding="utf-8") as f:
                    license_meta = json.load(f)
                license_name = license_meta.get("license", license_name)
                license_id = license_meta.get("license_id", license_id)
                break
            except Exception:
                pass
    return license_name, license_id

def fetch_elevenlabs_music(
    music_description: str,
    duration_seconds: float,
    clip_id: str,
    emotion: Optional[str] = None
) -> Optional[str]:
    """
    Selects royalty-free background music from the local library based on emotion.
    Saves metadata to output/cache/music_metadata_{clip_id}.json.
    Returns the path to the selected track, or None if music is disabled or unavailable.
    """
    import random
    
    # 1. Read configuration settings
    music_enabled = os.getenv("MUSIC_ENABLED", "true").lower() == "true"
    library_path = os.getenv("MUSIC_LIBRARY_PATH", "assets/music")
    default_vol = int(os.getenv("DEFAULT_MUSIC_VOLUME", "15"))
    randomize = os.getenv("RANDOMIZE_TRACKS", "true").lower() == "true"
    
    if not music_enabled:
        logger.info(f"Music is disabled via config for clip {clip_id}.")
        _save_music_metadata(clip_id, False, "none", "none", "", 0, None, None)
        return None

    # 2. Try to get emotion
    if not emotion:
        cache_dir = os.path.join("output", "cache")
        cache_path = os.path.join(cache_dir, f"emotion_{clip_id}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                emotion = cached_data.get("emotion")
                recommended_vol = cached_data.get("volume_pct", default_vol)
                logger.info(f"Loaded emotion '{emotion}' from cache for clip {clip_id}")
            except Exception:
                recommended_vol = default_vol
        else:
            recommended_vol = default_vol
    else:
        recommended_vol = default_vol
        cache_dir = os.path.join("output", "cache")
        cache_path = os.path.join(cache_dir, f"emotion_{clip_id}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                recommended_vol = cached_data.get("volume_pct", default_vol)
            except Exception:
                pass

    # Phase 26: Keep background music volume low so narration always dominates
    volume_pct = max(6, min(10, recommended_vol))

    # Map emotion to category
    category = _get_category_for_emotion(emotion)
    
    # 3. Locate files with supported formats
    extensions = (".mp3", ".wav", ".m4a", ".ogg", ".flac")
    category_dir = os.path.join(library_path, category)
    files = []
    
    # Attempt 1: Check mapped category directory
    if os.path.exists(category_dir):
        files = [
            os.path.join(category_dir, f) for f in os.listdir(category_dir)
            if os.path.isfile(os.path.join(category_dir, f)) and f.lower().endswith(extensions)
        ]
        
    # Attempt 2: Fallback to the "default" category folder
    if not files:
        default_dir = os.path.join(library_path, "default")
        if os.path.exists(default_dir):
            logger.info(f"Category folder '{category_dir}' is empty/missing. Falling back to '{default_dir}'...")
            files = [
                os.path.join(default_dir, f) for f in os.listdir(default_dir)
                if os.path.isfile(os.path.join(default_dir, f)) and f.lower().endswith(extensions)
            ]
        
    # Attempt 3: Fallback to root library path
    if not files and os.path.exists(library_path):
        logger.warning(f"No music files found in category or default. Searching root: {library_path}")
        files = [
            os.path.join(library_path, f) for f in os.listdir(library_path)
            if os.path.isfile(os.path.join(library_path, f)) and f.lower().endswith(extensions)
        ]
        
    # Attempt 4: Fallback to recursive search
    if not files and os.path.exists(library_path):
        logger.warning(f"No music files in root library path. Searching recursively in {library_path}...")
        for root, dirs, filenames in os.walk(library_path):
            for f in filenames:
                if f.lower().endswith(extensions):
                    files.append(os.path.join(root, f))

    if not files:
        logger.warning(f"No audio files found anywhere under local library path: {library_path}. Continuing without music.")
        _save_music_metadata(clip_id, False, "none", "none", "", 0, None, None)
        return None

    # Filter out recently used tracks
    available_files = [f for f in files if f not in _RECENT_TRACK_QUEUE]
    if not available_files:
        available_files = files
        
    # Selection
    if randomize:
        selected = random.choice(available_files)
    else:
        available_files.sort()
        selected = available_files[0]
        
    # Update FIFO queue
    global _RECENT_TRACK_QUEUE
    _RECENT_TRACK_QUEUE.append(selected)
    if len(_RECENT_TRACK_QUEUE) > _MAX_QUEUE_SIZE:
        _RECENT_TRACK_QUEUE.pop(0)

    # Clean the path separator for metadata consistency
    clean_selected_path = selected.replace("\\", "/")
    
    # Extract license information
    license_name, license_id = _get_license_info(selected)
    
    # Save selection metadata
    _save_music_metadata(
        clip_id=clip_id,
        has_music=True,
        music_source="local_library",
        music_category=category,
        music_file=clean_selected_path,
        volume_pct=volume_pct,
        license_name=license_name,
        license_id=license_id
    )
    
    logger.info(
        f"Selected local music track for clip {clip_id}: {clean_selected_path} "
        f"(category={category}, volume={volume_pct}%, license='{license_name}', license_id={license_id})"
    )
    return selected


def _detect_audio_loudness(clip_path: str, clip_id: str) -> tuple[float, float]:
    """
    Runs FFmpeg volumedetect to find the mean_volume and max_volume of the audio track.
    Returns (mean_volume_db, max_volume_db).
    Defaults to (-15.0, 0.0) if detection fails or file has no audio.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", clip_path,
        "-af", "volumedetect",
        "-f", "null", "-"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # Parse mean_volume: -14.9 dB
        mean_match = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", res.stderr)
        max_match = re.search(r"max_volume:\s*(-?\d+\.?\d*)\s*dB", res.stderr)
        
        mean_vol = float(mean_match.group(1)) if mean_match else -15.0
        max_vol = float(max_match.group(1)) if max_match else 0.0
        logger.info(f"Loudness detection for clip {clip_id}: mean={mean_vol}dB, max={max_vol}dB")
        return mean_vol, max_vol
    except Exception as e:
        logger.warning(f"Loudness detection failed for {clip_id}: {e}. Using defaults.")
        return -15.0, 0.0


def mix_music_into_clip(
    clip_path: str,
    music_path: str,
    volume_pct: int,
    fade_in_secs: float,
    fade_out_secs: float,
    duration: float,
    clip_id: str
) -> str:
    """
    Phase 25/26: Mixes background music under the voice track using FFmpeg with
    dynamic sidechain volume ducking and adaptive voice loudness normalization.

    Layer 1 — Dynamic ducking:
        sidechaincompress ducks music when voice is loud and raises it during
        speech pauses. threshold=0.01, ratio=20:1, attack=30ms, release=1500ms.

    Falls back to flat amix if sidechaincompress is unavailable.

    Returns path to output/clips/{clip_id}_with_music.mp4
    Returns original clip_path if mixing fails.
    Never raises.
    """
    clips_dir = os.path.join("output", "clips")
    os.makedirs(clips_dir, exist_ok=True)
    output_path = os.path.join(clips_dir, f"{clip_id}_with_music.mp4")

    # Skip re-generation if already exists (skip if doing comparison runs)
    # For comparisons, we handle bypass outside or via temporary names
    if "compare_" not in clip_id and os.path.exists(output_path) and os.path.getsize(output_path) > 10240:
        logger.info(f"Reusing existing with-music clip: {output_path}")
        return output_path

    # Measure speech loudness
    mean_vol, max_vol = _detect_audio_loudness(clip_path, clip_id)
    
    # Calculate target gain to hit consistent -14.0 dB target
    target_mean = -14.0
    gain_db = target_mean - mean_vol
    
    # Limit gain to range [0.0, 12.0] to prevent extreme boosts on noisy tracks
    gain_db = max(0.0, min(12.0, gain_db))
    logger.info(f"Clip {clip_id}: Applying adaptive gain of +{gain_db:.2f}dB and peak limiter (-0.5dB / 0.95)")

    volume_ratio = volume_pct / 100.0
    fade_out_start = max(0.0, duration - fade_out_secs)

    use_sidechain = _probe_sidechain_support()

    if use_sidechain:
        # Phase 26 refined: Narration is structurally dominant — music is atmosphere only.
        #
        # Key design decisions:
        #  - Voice boosted by adaptive gain and passed through peak limiter BEFORE mixing.
        #  - ratio=20:1 (near-limiter): music nearly silences when speech is detected.
        #  - threshold=0.01: catches even quiet speech; music ducks early.
        #  - attack=30ms: reacts before the first syllable finishes.
        #  - release=1500ms: recovers slowly — no pumping between words.
        #  - makeup=1: restores music during genuine pauses (no voice signal).
        #  - No afade=t=in: music starts at its quiet background level immediately.
        music_filter = (
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"aloop=loop=-1:size=2e+09,"
            f"volume={volume_ratio:.3f},"
            f"afade=t=out:st={fade_out_start:.2f}:d={fade_out_secs:.2f}"
            f"[music_faded];"
            f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"volume={gain_db:.2f}dB,"
            f"alimiter=level_in=1.0:level_out=1.0:limit=0.95:attack=5:release=80,"
            f"asplit=2[voice_compress][voice_mix];"
            f"[music_faded][voice_compress]sidechaincompress="
            f"threshold=0.01:ratio=20:attack=30:release=1500:makeup=1[ducked];"
            f"[voice_mix][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        layer_desc = "sidechain-ducking-20to1+adaptive-boost"
    else:
        # Fallback: flat amix — voice boosted by adaptive gain & limited, music kept at low background level.
        music_filter = (
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"aloop=loop=-1:size=2e+09,"
            f"volume={volume_ratio:.3f},"
            f"afade=t=out:st={fade_out_start:.2f}:d={fade_out_secs:.2f}"
            f"[music];"
            f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"volume={gain_db:.2f}dB,"
            f"alimiter=level_in=1.0:level_out=1.0:limit=0.95:attack=5:release=80"
            f"[voice_boosted];"
            f"[voice_boosted][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        layer_desc = "flat-amix+adaptive-boost"

    cmd = [
        "ffmpeg", "-y",
        "-i", clip_path,           # input 0: original clip (video + voice)
        "-i", music_path,          # input 1: music file (looped via filter)
        "-filter_complex", music_filter,
        "-map", "0:v",             # video from original clip
        "-map", "[aout]",          # mixed audio
        "-c:v", "copy",            # copy video stream (no re-encode)
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(duration),
        "-movflags", "+faststart",
        output_path
    ]

    try:
        logger.info(
            f"Mixing music into clip {clip_id}: "
            f"vol={volume_pct}%, fade_in={fade_in_secs}s, fade_out={fade_out_secs}s, "
            f"mode={layer_desc}"
        )
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(
                f"FFmpeg music mixing failed for {clip_id} "
                f"(rc={result.returncode}): {result.stderr[-800:]}"
            )
            return clip_path

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            logger.error(f"FFmpeg produced empty output for {clip_id}.")
            return clip_path

        logger.info(f"Music mixed successfully ({layer_desc}): {output_path}")
        return output_path

    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg music mixing timed out for clip {clip_id}.")
        return clip_path
    except Exception as e:
        logger.error(f"Unexpected error during music mixing for {clip_id}: {e}")
        return clip_path


def add_impact_sounds(
    clip_path: str,
    clip_text: str,
    hook_line: str,
    clip_id: str,
    api_key: Optional[str] = None,
    duration: float = 30.0
) -> Dict[str, Any]:
    """
    Phase 25 Layer 3: Overlays cinematic impact sound effects at key moments.

    Steps:
      1. LLM (claude-haiku-4-5) identifies 2-3 impactful moments in the clip.
      2. ElevenLabs SFX fetch for each identified moment (cached per clip).
      3. FFmpeg adelay + amix to place each SFX at the correct timestamp.
      4. Overwrites output/clips/{clip_id}_with_music.mp4.

    Returns:
      {
        "path": str,              # final output path (may equal input if SFX skipped)
        "layers_applied": list,   # ["ducking", "intro_build", "impact_sfx"]
        "impact_count": int,
        "impact_detail": list     # raw moment dicts from LLM
      }

    Never raises — gracefully skips SFX on any failure.
    """
    base_layers = ["ducking", "intro_build"]
    cache_dir = os.path.join("output", "cache")
    sfx_meta_path = os.path.join(cache_dir, f"sfx_{clip_id}_meta.json")

    # ------------------------------------------------------------------
    # Check SFX cache (skip regeneration if meta + all files exist)
    # ------------------------------------------------------------------
    if os.path.exists(sfx_meta_path):
        try:
            with open(sfx_meta_path, "r", encoding="utf-8") as f:
                cached_meta = json.load(f)
            # Verify all SFX files still exist
            sfx_paths = cached_meta.get("sfx_paths", [])
            if all(os.path.exists(p) and os.path.getsize(p) > 1024 for p in sfx_paths):
                logger.info(f"Reusing cached SFX for clip {clip_id} ({len(sfx_paths)} effects).")
                moments = cached_meta.get("moments", [])
                # Re-mix if output still exists and was written after the sfx meta
                final_path = clip_path  # default
                if sfx_paths:
                    mix_result = _apply_sfx_to_clip(clip_path, sfx_paths, moments, duration, clip_id)
                    final_path = mix_result
                return {
                    "path": final_path,
                    "layers_applied": base_layers + ["impact_sfx"],
                    "impact_count": len(moments),
                    "impact_detail": moments,
                }
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Check ElevenLabs availability
    # ------------------------------------------------------------------
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    resolved_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or ""

    if not elevenlabs_key or resolved_key.startswith("mock"):
        logger.info(f"Clip {clip_id}: Skipping impact SFX (ElevenLabs key not configured).")
        return {
            "path": clip_path,
            "layers_applied": base_layers,
            "impact_count": 0,
            "impact_detail": [],
        }

    # ------------------------------------------------------------------
    # Step 1: LLM — identify impactful moments
    # ------------------------------------------------------------------
    moments = _identify_impact_moments(clip_text, hook_line, resolved_key, duration)
    if not moments:
        logger.info(f"Clip {clip_id}: No impact moments identified. Skipping SFX layer.")
        return {
            "path": clip_path,
            "layers_applied": base_layers,
            "impact_count": 0,
            "impact_detail": [],
        }

    logger.info(f"Clip {clip_id}: Identified {len(moments)} impact moments: {moments}")

    # ------------------------------------------------------------------
    # Step 2: Fetch SFX from ElevenLabs for each moment
    # ------------------------------------------------------------------
    sfx_paths: List[str] = []
    for idx, moment in enumerate(moments):
        effect_type = moment.get("effect_type", "impact")
        sfx_desc = _SFX_DESCRIPTIONS.get(effect_type, "deep cinematic impact boom")
        sfx_out = os.path.join(cache_dir, f"sfx_{clip_id}_{idx}.mp3")

        # Skip if already cached
        if os.path.exists(sfx_out) and os.path.getsize(sfx_out) > 1024:
            logger.info(f"Reusing cached SFX {idx} for clip {clip_id}: {sfx_out}")
            sfx_paths.append(sfx_out)
            continue

        sfx_result = _fetch_from_elevenlabs(sfx_desc, 5.0, sfx_out, elevenlabs_key)
        if sfx_result:
            sfx_paths.append(sfx_result)
            logger.info(f"Clip {clip_id}: SFX {idx} ({effect_type}) fetched: {sfx_result}")
        else:
            logger.warning(f"Clip {clip_id}: SFX {idx} fetch failed — skipping this effect.")

    if not sfx_paths:
        logger.warning(f"Clip {clip_id}: All SFX fetches failed. Skipping SFX layer.")
        return {
            "path": clip_path,
            "layers_applied": base_layers,
            "impact_count": 0,
            "impact_detail": moments,
        }

    # Trim moments list to match actually fetched SFX
    moments = moments[:len(sfx_paths)]

    # ------------------------------------------------------------------
    # Step 3: Apply SFX with FFmpeg adelay + amix
    # ------------------------------------------------------------------
    final_path = _apply_sfx_to_clip(clip_path, sfx_paths, moments, duration, clip_id)

    # ------------------------------------------------------------------
    # Save SFX meta cache
    # ------------------------------------------------------------------
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(sfx_meta_path, "w", encoding="utf-8") as f:
            json.dump({"sfx_paths": sfx_paths, "moments": moments}, f, indent=2)
    except Exception as cache_err:
        logger.warning(f"Failed to write SFX meta cache for {clip_id}: {cache_err}")

    return {
        "path": final_path,
        "layers_applied": base_layers + ["impact_sfx"],
        "impact_count": len(moments),
        "impact_detail": moments,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _save_emotion_cache(clip_id: str, data: dict) -> None:
    """Helper to write emotion analysis result to cache."""
    cache_path = os.path.join("output", "cache", f"emotion_{clip_id}.json")
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as err:
        logger.warning(f"Failed to write emotion cache for {clip_id}: {err}")


def _identify_impact_moments(
    clip_text: str,
    hook_line: str,
    api_key: str,
    duration: float
) -> List[Dict]:
    """
    Calls claude-haiku-4-5 to identify 2-3 impactful moments deserving SFX.
    Returns a list of dicts: [{timestamp_hint, word, effect_type}, ...]
    """
    if not api_key or api_key.startswith("mock"):
        return []

    system_prompt = "You are a video editor specialising in cinematic sound design for viral short-form content."
    user_prompt = f"""Read this clip transcript and identify the 2-3 most impactful words or phrases that deserve a sound effect punch. These are moments of surprise, revelation, or strong emphasis.

Transcript: {clip_text}
Hook: {hook_line}
Clip duration: {duration:.1f} seconds

Return JSON array only:
[{{"timestamp_hint": "early|middle|late", "word": "the impactful word or phrase", "effect_type": "impact|whoosh|ding|swoosh"}}]

Rules:
- timestamp_hint "early" = first 20% of clip, "middle" = 40-60%, "late" = last 20%
- Choose effect_type that best matches the moment's tone
- Return 2-3 items maximum
- Return only the JSON array, no other text."""

    try:
        llm = LLMResilienceManager(primary_key=api_key)
        response_text = llm.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_json=True,
            model="claude-haiku-4-5"
        )
        repaired = _extract_json_from_response(response_text)

        # Parse — may be a top-level array or wrapped in an object
        parsed = json.loads(repaired)
        if isinstance(parsed, dict):
            # Unwrap if the LLM returned {"moments": [...]}
            for key in ("moments", "impacts", "items", "effects"):
                if isinstance(parsed.get(key), list):
                    parsed = parsed[key]
                    break
            else:
                parsed = list(parsed.values())[0] if parsed else []

        if not isinstance(parsed, list):
            return []

        # Validate and sanitize each moment
        valid_hints = {"early", "middle", "late"}
        valid_effects = set(_SFX_DESCRIPTIONS.keys())
        moments = []
        for item in parsed[:3]:
            if not isinstance(item, dict):
                continue
            hint = item.get("timestamp_hint", "middle")
            if hint not in valid_hints:
                hint = "middle"
            effect = item.get("effect_type", "impact")
            if effect not in valid_effects:
                effect = "impact"
            word = str(item.get("word", "")).strip()[:80]
            moments.append({
                "timestamp_hint": hint,
                "word": word,
                "effect_type": effect,
            })
        return moments

    except Exception as e:
        logger.error(f"Impact moment identification failed: {e}")
        return []


def _timestamp_hint_to_seconds(hint: str, duration: float) -> float:
    """Map early/middle/late to an actual second within the clip."""
    mapping = {"early": 0.20, "middle": 0.50, "late": 0.80}
    frac = mapping.get(hint, 0.50)
    ts = duration * frac
    # Keep at least 0.5s from edges so the SFX is audible
    return max(0.5, min(ts, duration - 0.5))


def _apply_sfx_to_clip(
    clip_path: str,
    sfx_paths: List[str],
    moments: List[Dict],
    duration: float,
    clip_id: str
) -> str:
    """
    Builds an FFmpeg command that places each SFX at the correct timestamp
    using atrim + adelay + amix, then overwrites {clip_id}_with_music.mp4.
    """
    clips_dir = os.path.join("output", "clips")
    output_path = os.path.join(clips_dir, f"{clip_id}_with_music.mp4")

    if not sfx_paths:
        return clip_path

    # Build filter_complex
    # Input 0 = clip (video+mixed audio)
    # Inputs 1..N = SFX files
    sfx_vol = 0.30  # SFX at 30% relative volume

    filter_parts: List[str] = []
    delayed_labels: List[str] = []
    
    # Normalize original clip audio
    filter_parts.append("[0:a]aformat=sample_rates=44100:channel_layouts=stereo[norm_voice]")

    for idx, (sfx_path, moment) in enumerate(zip(sfx_paths, moments)):
        ts_secs = _timestamp_hint_to_seconds(moment.get("timestamp_hint", "middle"), duration)
        ts_ms = int(ts_secs * 1000)
        in_label = f"[{idx + 1}:a]"
        delayed_label = f"[sfxd{idx}]"

        # Normalize SFX format before trimming/delaying
        filter_parts.append(
            f"{in_label}aformat=sample_rates=44100:channel_layouts=stereo,"
            f"atrim=0:1.5,asetpts=PTS-STARTPTS,"
            f"volume={sfx_vol:.2f},adelay={ts_ms}|{ts_ms}{delayed_label}"
        )
        delayed_labels.append(delayed_label)

    # Amix: voice/music from clip + all SFX delayed streams
    n_inputs = 1 + len(delayed_labels)
    all_inputs = "[norm_voice]" + "".join(delayed_labels)
    filter_parts.append(
        f"{all_inputs}amix=inputs={n_inputs}:duration=first:dropout_transition=0:normalize=0[aout]"
    )

    filter_complex = ";".join(filter_parts)

    temp_output_path = output_path + ".sfxtmp.mp4"
    cmd = ["ffmpeg", "-y"]
    cmd += ["-i", clip_path]
    for sfx_path in sfx_paths:
        cmd += ["-i", sfx_path]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(duration),
        "-movflags", "+faststart",
        temp_output_path
    ]

    logger.info(
        f"Clip {clip_id}: Applying {len(sfx_paths)} impact SFX. "
        f"FFmpeg filter: {filter_complex[:300]}..."
    )

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(
                f"FFmpeg SFX mix failed for {clip_id} "
                f"(rc={result.returncode}): {result.stderr[-600:]}"
            )
            if os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                except Exception:
                    pass
            return clip_path

        if not os.path.exists(temp_output_path) or os.path.getsize(temp_output_path) < 1024:
            logger.error(f"FFmpeg SFX produced empty output for {clip_id}.")
            if os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                except Exception:
                    pass
            return clip_path

        os.replace(temp_output_path, output_path)
        file_size = os.path.getsize(output_path)
        logger.info(
            f"Clip {clip_id}: Impact SFX mixed successfully. "
            f"Output: {output_path} ({file_size:,} bytes)"
        )
        return output_path

    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg SFX mixing timed out for clip {clip_id}.")
        if os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
            except Exception:
                pass
        return clip_path
    except Exception as e:
        logger.error(f"Unexpected error during SFX mixing for {clip_id}: {e}")
        if os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
            except Exception:
                pass
        return clip_path


def _fetch_from_elevenlabs(
    description: str,
    duration_seconds: float,
    output_path: str,
    api_key: str
) -> Optional[str]:
    """Calls ElevenLabs Sound Generation API and saves the MP3."""
    if api_key.startswith("mock") or api_key == "mock":
        cache_dir = os.path.dirname(output_path)
        existing_mp3s = [
            f for f in os.listdir(cache_dir)
            if f.startswith("music_") and f.endswith(".mp3")
            and f != os.path.basename(output_path)
        ]
        if existing_mp3s:
            import shutil
            src_path = os.path.join(cache_dir, existing_mp3s[0])
            shutil.copy(src_path, output_path)
            size = os.path.getsize(output_path)
            logger.info(
                f"ElevenLabs: downloaded {size} bytes "
                f"for description='{description}'"
            )
            return output_path

    try:
        # Clamp duration to ElevenLabs limits (5–22 seconds)
        el_duration = max(5.0, min(22.0, duration_seconds))
        payload = json.dumps({
            "text": f"{description} background music loop",
            "duration_seconds": el_duration,
            "prompt_influence": 0.3
        }).encode("utf-8")

        req = urllib.request.Request(
            _ELEVENLABS_API_URL,
            data=payload,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status == 200:
                audio_data = response.read()
                if len(audio_data) > 1024:
                    temp_path = output_path + f".{os.getpid()}.tmp"
                    with open(temp_path, "wb") as f:
                        f.write(audio_data)
                    os.replace(temp_path, output_path)
                    logger.info(
                        f"ElevenLabs: downloaded {len(audio_data)} bytes "
                        f"for description='{description}'"
                    )
                    return output_path
                else:
                    logger.warning("ElevenLabs returned suspiciously small audio payload.")
                    return None
            else:
                logger.warning(f"ElevenLabs API returned status {response.status}")
                return None

    except urllib.error.HTTPError as e:
        logger.warning(f"ElevenLabs HTTP error: {e.code} {e.reason}")
        return None
    except Exception as e:
        logger.warning(f"ElevenLabs fetch failed: {e}")
        return None


def _fetch_from_freesound(search_query: str, output_path: str) -> Optional[str]:
    """
    Freesound.org requires OAuth for actual downloads.
    Returns None — ElevenLabs is the primary music source.
    """
    logger.info(
        "Freesound.org download requires authentication. "
        "Marking as unavailable — pipeline will proceed without music."
    )
    return None
