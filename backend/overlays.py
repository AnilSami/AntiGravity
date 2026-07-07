"""
overlays.py — Phase 26: Animated Like Button Overlay

Renders a professional animated Like button overlay on every generated Short.

Appearance schedule (3 times per clip):
  T1 ~ 12% of duration   (beginning)
  T2 ~ 50% of duration   (middle)
  T3 ~ 87% of duration   (end)

Custom asset priority (checked before FFmpeg fallback):
  assets/animations/like_button.mp4   (preferred — alpha channel if VP9)
  assets/animations/like_button.webm  (WebM with alpha)
  assets/animations/like_button.gif   (GIF, no alpha)

FFmpeg fallback animation (no asset found):
  Layered drawbox (ripple ring) + drawtext (👍 LIKE) with alpha-driven
  fade-in / hold / fade-out expressions. Each appearance is 1.5s.

Position: left-of-center, upper-third  (x≈8%, y≈30% of height)
  - Avoids face area (typically centered/right on talking-head Shorts)
  - Avoids subtitle zone (bottom 25%)

Click sound: like_ding.mp3 at 12% volume, fired at each T1/T2/T3.
"""

import os
import logging
import subprocess
from typing import Optional, List

logger = logging.getLogger("overlays")

# ---------------------------------------------------------------------------
# Font detection
# ---------------------------------------------------------------------------

def _get_font_param() -> str:
    """Returns the drawtext fontfile parameter based on platform availability."""
    paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in paths:
        if os.path.exists(p):
            clean_p = p.replace("\\", "/")
            if ":" in clean_p:
                parts = clean_p.split(":", 1)
                clean_p = f"{parts[0]}\\:{parts[1]}"
            return f"fontfile='{clean_p}':"
    return ""  # Fallback: use FFmpeg default font


# ---------------------------------------------------------------------------
# Custom asset detection
# ---------------------------------------------------------------------------

def _find_custom_asset() -> Optional[str]:
    """
    Returns the path to a custom Like button animation asset if one exists,
    otherwise None. Priority: webm → mp4 → gif.
    """
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(backend_dir)
    anim_dir = os.path.join(root_dir, "assets", "animations")
    for ext in ("webm", "mp4", "gif"):
        candidate = os.path.join(anim_dir, f"like_button.{ext}")
        if os.path.exists(candidate) and os.path.getsize(candidate) > 512:
            logger.info(f"Found custom Like animation asset: {candidate}")
            return candidate
    return None


def _get_video_width(video_path: str) -> int:
    """Gets the width of the video in pixels using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width",
        "-of", "csv=p=0",
        video_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return int(res.stdout.strip())
    except Exception as e:
        logger.error(f"Error getting video width for '{video_path}': {e}")
        return 1080  # Default fallback


def _has_alpha_channel(asset_path: str) -> bool:
    """
    Checks if the given asset has an alpha/transparency channel using ffprobe.
    Detects tags like alpha_mode=1 (VP9 WebM), pixel formats with alpha
    (yuva, rgba, bgra, argb), and specific transparent format/codec names.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_streams", "-show_format",
        asset_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        out = res.stdout.lower()
        if "alpha_mode=1" in out or "yuva" in out or "rgba" in out or "bgra" in out or "argb" in out:
            logger.info(f"Asset '{asset_path}' has alpha channel (detected from streams info).")
            return True
        # Also check transparent formats/codecs
        if "codec_name=gif" in out or "codec_name=png" in out:
            logger.info(f"Asset '{asset_path}' is transparent GIF/PNG (detected from codec info).")
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking alpha channel for '{asset_path}' via ffprobe: {e}")
        return False


# ---------------------------------------------------------------------------
# FFmpeg filter builders
# ---------------------------------------------------------------------------

def _build_drawtext_segment(
    font_param: str,
    text_file_ffmpeg: str,
    t_start: float,
    duration_each: float = 1.5,
) -> str:
    """
    Returns a single drawtext filter that shows '👍 LIKE' for `duration_each`
    seconds starting at `t_start` with:
      - Smooth slide-in from left (0.0s to 0.3s)
      - Subtle bounce (vertical hop) on entry and exit
      - Modern semi-transparent dark card background (box=1)
      - Smooth slide-out to left (duration-0.3s to duration)
    """
    t_end = t_start + duration_each

    # Slide-in/out: x goes from (w*0.06 - 300) to w*0.06
    x_expr = (
        f"if(lt(t,{t_start:.3f}),-500,"
        f"if(lt(t,{t_start+0.3:.3f}),w*0.06-300*(1-(t-{t_start:.3f})/0.3),"
        f"if(lt(t,{t_end-0.3:.3f}),w*0.06,"
        f"if(lt(t,{t_end:.3f}),w*0.06-300*((t-({t_end-0.3:.3f}))/0.3),-500))))"
    )

    # Vertical bounce: subtle hop on entry/exit using sine wave
    y_expr = (
        f"if(lt(t,{t_start:.3f}),h*0.08,"
        f"if(lt(t,{t_start+0.3:.3f}),h*0.08-15*sin((t-{t_start:.3f})*PI/0.3),"
        f"if(lt(t,{t_end-0.3:.3f}),h*0.08,"
        f"if(lt(t,{t_end:.3f}),h*0.08-10*sin((t-({t_end-0.3:.3f}))*PI/0.3),h*0.08))))"
    )

    # Fade in/out
    alpha_expr = (
        f"if(lt(t,{t_start:.3f}),0,"
        f"if(lt(t,{t_start+0.3:.3f}),(t-{t_start:.3f})/0.3,"
        f"if(lt(t,{t_end-0.3:.3f}),1,"
        f"if(lt(t,{t_end:.3f}),({t_end:.3f}-t)/0.3,0))))"
    )

    # Create the filter string (reduced fontsize to 32 and boxborderw to 8 to keep it small and clean)
    segment_filter = (
        f"drawtext={font_param}textfile='{text_file_ffmpeg}':"
        f"x='{x_expr}':y='{y_expr}':"
        f"fontsize=32:fontcolor=white:bordercolor=black:borderw=2:"
        f"box=1:boxcolor=black@0.60:boxborderw=8:"
        f"alpha='{alpha_expr}'"
    )
    return segment_filter


def _build_ffmpeg_video_filter(
    font_param: str,
    text_file_ffmpeg: str,
    timestamps: List[float],
) -> str:
    """
    Chains all appearance segments into a single filter_complex video chain.
    Input label [0:v], output label [vout].
    """
    M = len(timestamps)
    if M == 0:
        return "[0:v]copy[vout]"

    # Each appearance segment lasts 2.5s (matching the extended duration request)
    segs = [
        _build_drawtext_segment(font_param, text_file_ffmpeg, t, duration_each=2.5)
        for t in timestamps
    ]

    parts = []
    prev_label = "0:v"
    for i in range(M):
        out_label = f"v{i + 1}" if i < M - 1 else "vout"
        parts.append(f"[{prev_label}]{segs[i]}[{out_label}]")
        prev_label = out_label

    return ";".join(parts)


def _build_custom_asset_filter(
    asset_path: str,
    timestamps: List[float],
    video_width: int,
) -> str:
    """
    Builds a filter_complex that overlays a custom animation asset
    (mp4/webm/gif) using independent time-shifted, slowed-down, and scaled streams
    for each appearance.

    Each appearance lasts 2.37s (1.58s WebM slowed down 1.5x for smoother motion).
    The overlay is scaled to 12% of the video width (preserving aspect ratio)
    and placed at the top-left padding position (x=W*0.06:y=H*0.08).

    Input: [0:v] (base video), [1:v] (asset, looped)
    Output: [vout]
    """
    has_alpha = _has_alpha_channel(asset_path)
    M = len(timestamps)
    if M == 0:
        return "[0:v]copy[vout]"

    duration_each = 2.37  # 1.58s slowed down by 1.5x
    target_w = int(video_width * 0.12)
    target_w = (target_w // 2) * 2  # Ensure even width for YUV420p compliance

    filter_parts = []

    # 1. Base input processing: colorkeying if no alpha channel
    if has_alpha:
        base_asset = "[1:v]"
    else:
        key_color = os.getenv("LIKE_OVERLAY_KEY_COLOR", "white").strip()
        similarity = os.getenv("LIKE_OVERLAY_SIMILARITY", "0.01").strip()
        blend = os.getenv("LIKE_OVERLAY_BLEND", "0.05").strip()
        base_asset = f"[1:v]colorkey=color={key_color}:similarity={similarity}:blend={blend}"

    # 2. Split the asset stream so each appearance can have its own shifted PTS playhead
    if M > 1:
        filter_parts.append(f"{base_asset}split={M}" + "".join(f"[c{i}]" for i in range(M)))
    else:
        filter_parts.append(f"{base_asset}copy[c0]")

    # 3. Time-shift, scale (Lanczos), and overlay each appearance
    prev_label = "0:v"
    for i, t in enumerate(timestamps):
        out_label = f"v{i + 1}" if i < M - 1 else "vout"
        
        # Slow down playhead 1.5x and align start frame with t
        setpts_expr = f"1.5*(PTS-STARTPTS)+{t}/TB"
        
        # Shift PTS and scale to 12% width (preserving aspect ratio with -2 height)
        # Note: we use lanczos scaling for maximum visual quality
        filter_parts.append(
            f"[c{i}]setpts={setpts_expr},scale={target_w}:-2:flags=lanczos[scaled{i}]"
        )
        
        enable_expr = f"between(t,{t:.3f},{t + duration_each:.3f})"
        overlay = (
            f"[{prev_label}][scaled{i}]overlay="
            f"x=W*0.06:y=H*0.08:"
            f"enable='{enable_expr}'[{out_label}]"
        )
        filter_parts.append(overlay)
        prev_label = out_label

    return ";".join(filter_parts)


# ---------------------------------------------------------------------------
# Ding / click sound management
# ---------------------------------------------------------------------------

def _find_click_sound() -> Optional[str]:
    """
    Finds and returns the absolute path to assets/sfx/like_click.mp3 if it exists,
    otherwise returns None and logs a warning.
    """
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(backend_dir)
    click_path = os.path.join(root_dir, "assets", "sfx", "like_click.mp3")
    if os.path.exists(click_path) and os.path.getsize(click_path) > 1024:
        return click_path

    # Fallback to local relative lookup
    local_path = os.path.join("assets", "sfx", "like_click.mp3")
    if os.path.exists(local_path) and os.path.getsize(local_path) > 1024:
        return os.path.abspath(local_path)

    logger.warning("Like click sound effect file (assets/sfx/like_click.mp3) is missing.")
    return None


def _build_audio_filter(
    click_path: Optional[str],
    timestamps: List[float],
    first_ding_input: int,
    use_custom: bool,
) -> tuple:
    """
    Returns (audio_filter_complex_part, map_audio_label, extra_input_args).
    The click is played at each timestamp at a synchronized delay:
      - Custom asset: click/pop frame is at 0.40s. The sound contact transient starts at 0.08s,
        so we offset by (0.40 - 0.08) = 0.32s to align the audio transient.
      - Fallback asset: text card slides in and settles at 0.30s. The sound contact transient starts at 0.08s,
        so we offset by (0.30 - 0.08) = 0.22s to align the audio transient.
    Volume is set to 9% (0.09) of narration.
    Apply a 7ms fade-in and 7ms fade-out (st=0.393, d=0.007) to avoid audio clicks.
    """
    if not click_path or not timestamps:
        return "", "0:a", []

    extra_inputs = []
    click_labels = []
    for i, t in enumerate(timestamps):
        extra_inputs += ["-i", click_path]
        label = f"click{i}"
        click_labels.append(label)

    # Offset to align the click sound's contact transient (starts at 0.08s in assets/sfx/like_click.mp3)
    # with the visual click event.
    if use_custom:
        offset = 0.52
    else:
        offset = 0.22

    # Build filter parts: format, fade in (7ms), fade out (7ms starting at 0.393s), volume=0.09
    filter_parts = ["[0:a]aformat=sample_rates=44100:channel_layouts=stereo[voice_raw]"]
    for i, (t, label) in enumerate(zip(timestamps, click_labels)):
        idx = first_ding_input + i
        click_time = t + offset
        delay_ms = int(click_time * 1000)
        filter_parts.append(
            f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"afade=t=in:st=0:d=0.007,afade=t=out:st=0.393:d=0.007,"
            f"volume=0.09,"
            f"adelay={delay_ms}|{delay_ms}[{label}]"
        )

    all_labels = "[voice_raw]" + "".join(f"[{l}]" for l in click_labels)
    n_inputs = 1 + len(timestamps)
    filter_parts.append(
        f"{all_labels}amix=inputs={n_inputs}:duration=first:dropout_transition=0:normalize=0[aout]"
    )

    return ";".join(filter_parts), "[aout]", extra_inputs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_like_overlay(clip_path: str, clip_id: str, duration: float) -> str:
    """
    Phase 26: Adds an animated Like button overlay to the given clip.

    Appearance schedule (3 times):
      T1 ~ 12% of duration  (beginning)
      T2 ~ 50% of duration  (middle)
      T3 ~ 87% of duration  (end)

    Custom asset priority: mp4 → webm → gif → FFmpeg drawtext fallback.
    Click sound at 12% volume fired at each timestamp.

    Returns the path to the output file, or clip_path on failure.
    Output: output/clips/{clip_id}_with_music.mp4 (overwrites existing).
    """
    clips_dir = os.path.join("output", "clips")
    cache_dir = os.path.join("output", "cache")
    anim_dir = os.path.join("assets", "animations")
    os.makedirs(clips_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(anim_dir, exist_ok=True)

    output_path = os.path.join(clips_dir, f"{clip_id}_with_music.mp4")
    temp_path = output_path + ".liketmp.mp4"

    # Detect custom asset
    custom_asset = _find_custom_asset()
    use_custom = custom_asset is not None

    # Get video width to scale custom overlay dynamically
    video_width = _get_video_width(clip_path)

    # Determine animation duration to validate timestamps
    anim_dur = 2.37 if use_custom else 2.50

    # Determine raw timestamps based on adaptive event count rules
    if duration < 15.0:
        raw_timestamps = [duration * 0.50]
    elif duration <= 30.0:
        raw_timestamps = [duration * 0.25, duration * 0.75]
    else:
        raw_timestamps = [duration * 0.15, duration * 0.50, duration * 0.85]

    # Validate timestamps: must start >= 0.5s and end <= duration - 0.5s
    validated_timestamps = [
        t for t in raw_timestamps
        if t >= 0.5 and (t + anim_dur) <= (duration - 0.5)
    ]

    logger.info(
        f"Like overlay for clip {clip_id} (duration={duration:.1f}s): "
        f"adaptive count={len(raw_timestamps)}, validated={validated_timestamps}"
    )

    # Prepare text file (used only by FFmpeg fallback)
    text_file_path = os.path.join(cache_dir, "like_text.txt")
    if not use_custom and not os.path.exists(text_file_path):
        try:
            with open(text_file_path, "w", encoding="utf-8") as f:
                f.write("👍 LIKE")
        except Exception as e:
            logger.error(f"Failed to create like text file: {e}")

    text_file_ffmpeg = text_file_path.replace("\\", "/")

    # Prepare click sound
    click_path = _find_click_sound()

    # Determine first click input index
    # Base inputs: [0] = clip, [1] = custom asset (if any)
    first_click_input = 2 if use_custom else 1

    # Build audio filter using ONLY validated timestamps
    audio_filter_str, audio_map, extra_click_inputs = _build_audio_filter(
        click_path, validated_timestamps, first_click_input, use_custom
    )
    has_click = bool(click_path) and bool(validated_timestamps)

    # Build FFmpeg command
    cmd = ["ffmpeg", "-y"]
    cmd += ["-i", clip_path]  # Input 0: clip

    if use_custom:
        if custom_asset.endswith(".webm"):
            cmd += ["-c:v", "libvpx-vp9", "-stream_loop", "-1", "-i", custom_asset]  # Input 1: asset (looped with VP9 alpha)
        else:
            cmd += ["-stream_loop", "-1", "-i", custom_asset]  # Input 1: asset (looped)

    if has_click:
        cmd += extra_click_inputs  # Inputs for click sound

    # Build video filter using ONLY validated timestamps
    if use_custom:
        video_filter = _build_custom_asset_filter(custom_asset, validated_timestamps, video_width)
    else:
        font_param = _get_font_param()
        video_filter = _build_ffmpeg_video_filter(font_param, text_file_ffmpeg, validated_timestamps)

    # Combine video + audio into filter_complex
    if has_click:
        filter_complex = f"{video_filter};{audio_filter_str}"
    else:
        filter_complex = video_filter

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", audio_map,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(duration),
        "-movflags", "+faststart",
        temp_path,
    ]

    logger.info(
        f"Running Like overlay FFmpeg for {clip_id} "
        f"(custom_asset={use_custom}, has_click={has_click})"
    )

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            logger.error(
                f"FFmpeg Like overlay failed for {clip_id} "
                f"(rc={result.returncode}): {result.stderr[-800:]}"
            )
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return clip_path

        if not os.path.exists(temp_path) or os.path.getsize(temp_path) < 1024:
            logger.error(f"FFmpeg Like overlay produced empty output for {clip_id}.")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return clip_path

        os.replace(temp_path, output_path)
        logger.info(f"Like overlay applied successfully: {output_path}")
        return output_path

    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg Like overlay timed out for {clip_id}.")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return clip_path
    except Exception as e:
        logger.error(f"Unexpected error in Like overlay for {clip_id}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return clip_path
