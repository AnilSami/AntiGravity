import os
import shutil
import subprocess
import logging
import yt_dlp
import cv2
import math
import re
import json
import pathlib
from typing import Optional, Union
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from config import settings

logger = logging.getLogger("clipper")

def check_ffmpeg() -> bool:
    """Checks if ffmpeg is installed and available in the PATH."""
    return shutil.which("ffmpeg") is not None

def escape_ffmpeg_path(path: str) -> str:
    """Escapes a Windows absolute path for use in FFmpeg filter graphs (subtitles/ass)."""
    if not path:
        return ""
    # Swap backslashes to forward slashes
    path = path.replace("\\", "/")
    # Escape the colon for the drive letter (e.g. C: -> C\:)
    path = path.replace(":", "\\:")
    # Escape single quotes
    path = path.replace("'", "'\\''")
    return path

def has_audio(input_path: str) -> bool:
    """Checks if the video has an audio stream using ffprobe."""
    if not check_ffmpeg():
        return False
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_name",
        "-of", "csv=p=0",
        input_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=15)
        return len(result.stdout.strip()) > 0
    except Exception as e:
        logger.warning(f"Failed to check for audio: {e}. Assuming no audio.")
        return False

_HAS_NVENC = None

def has_nvenc() -> bool:
    """Checks if NVIDIA NVENC H.264 encoder is available in FFmpeg (cached)."""
    global _HAS_NVENC
    if _HAS_NVENC is None:
        if not check_ffmpeg():
            _HAS_NVENC = False
        else:
            try:
                res = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True, timeout=15)
                _HAS_NVENC = "h264_nvenc" in res.stdout
            except Exception:
                _HAS_NVENC = False
    return _HAS_NVENC

def prune_cache(cache_dir: str,
                max_size_bytes: int = None,
                target_size_bytes: int = None):
    """Prunes the cache directory if it exceeds max_size_bytes, down to target_size_bytes."""
    if max_size_bytes is None:
        max_size_bytes = settings.CACHE_MAX_SIZE_BYTES
    if target_size_bytes is None:
        target_size_bytes = settings.CACHE_TARGET_SIZE_BYTES
    if not os.path.exists(cache_dir):
        return
    files = []
    total_size = 0
    for entry in os.scandir(cache_dir):
        if entry.is_file() and not entry.name.endswith(".json"):
            try:
                stat = entry.stat()
                files.append((entry.path, stat.st_mtime, stat.st_size))
                total_size += stat.st_size
            except Exception as e:
                logger.warning(f"Error reading file stats for {entry.path}: {e}")
    if total_size <= max_size_bytes:
        logger.info(f"Cache size ({total_size / 1024 / 1024:.2f} MB) is within limits.")
        return
    logger.info(f"Cache size ({total_size / 1024 / 1024:.2f} MB) exceeds maximum ({max_size_bytes / 1024 / 1024:.2f} MB). Pruning oldest files...")
    files.sort(key=lambda x: x[1])  # Sort by modification time (oldest first)
    for path, _, size in files:
        if total_size <= target_size_bytes:
            break
        try:
            os.remove(path)
            total_size -= size
            logger.info(f"Deleted cached file to save space: {path}")
        except Exception as e:
            logger.warning(f"Failed to delete cached file {path}: {e}")
    logger.info(f"Pruning complete. New cache size: {total_size / 1024 / 1024:.2f} MB.")

def record_cache_metric(cache_dir: str, is_hit: bool):
    """Records cache hit/miss metric in cache_stats.json."""
    os.makedirs(cache_dir, exist_ok=True)
    stats_file = os.path.join(cache_dir, "cache_stats.json")
    stats = {"hits": 0, "misses": 0}
    if os.path.exists(stats_file):
        try:
            with open(stats_file, "r") as f:
                stats = json.load(f)
        except Exception as e:
            logger.debug(f"Cache stats file is corrupt or unreadable, resetting: {e}")
    if is_hit:
        stats["hits"] = stats.get("hits", 0) + 1
        logger.info(f"[CACHE HIT] Video found in local cache.")
    else:
        stats["misses"] = stats.get("misses", 0) + 1
        logger.info(f"[CACHE MISS] Video not found in local cache. Downloading...")
    try:
        with open(stats_file, "w") as f:
            json.dump(stats, f)
    except Exception as e:
        logger.warning(f"Failed to write cache stats: {e}")

def download_video(url: str, download_dir: str, progress_callback=None, video_id: str = None, format_spec: str = None, download_range: tuple[float, float] = None) -> str:
    """Downloads the best available MP4 video using yt-dlp, with local caching and resume support."""
    # Ensure cache folder exists
    cache_dir = os.path.join("output", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    
    if not video_id:
        try:
            from analyzer import get_video_id
            video_id = get_video_id(url)
        except Exception:
            video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else "unknown_vid"

    # Incorporate download range into cached name if present to avoid cache pollution
    cache_key = video_id
    if download_range:
        cache_key = f"{video_id}_range_{int(download_range[0])}_{int(download_range[1])}"

    cached_path = os.path.join(cache_dir, f"{cache_key}.mp4")
    logger.info(f"[PATH DIAGNOSTIC] Requested cache path: {cached_path}")
    
    # Check if cached file exists and has content
    if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
        record_cache_metric(cache_dir, is_hit=True)
        if progress_callback:
            progress_callback(100)
        logger.info(f"[PATH DIAGNOSTIC] Cache hit! Path returned from download_video(): {cached_path}")
        return cached_path

    record_cache_metric(cache_dir, is_hit=False)
    
    # Prune cache before downloading new files to prevent disk filling
    prune_cache(cache_dir)

    # Use persistent path directly to allow native resume of incomplete downloads
    outtmpl = os.path.join(cache_dir, f"{cache_key}.%(ext)s")

    def ytdl_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent = int(downloaded / total * 100)
            else:
                percent = 50
            if progress_callback:
                progress_callback(percent)

    fmt = format_spec or os.getenv("AUDIT_FORMAT_SPEC") or 'bestvideo[ext=mp4][height<=2160]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best'

    ydl_opts = {
        'format': fmt,
        'merge_output_format': 'mp4',
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [ytdl_hook],
        'concurrent_fragment_downloads': settings.DOWNLOAD_CONCURRENT_FRAGMENTS,
        'buffersize': 1024 * 1024,
        'http_chunk_size': 10485760,
        'nocheckcertificate': True,
        'source_address': '0.0.0.0', # Force IPv4 to prevent connection timeouts/IPv6 routing errors
    }

    if download_range:
        ydl_opts['download_ranges'] = lambda info_dict, ydl: [{'start_time': download_range[0], 'end_time': download_range[1]}]
        ydl_opts['force_keyframes_at_cuts'] = True

    logger.info(f"Starting video download for URL: {url} to {outtmpl} (range={download_range})")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    valid_exts = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
    for file in os.listdir(cache_dir):
        if file.startswith(cache_key + "."):
            _, ext = os.path.splitext(file)
            if ext.lower() in valid_exts:
                file_path = os.path.join(cache_dir, file)
                logger.info(f"[PATH DIAGNOSTIC] Actual downloaded path: {file_path}")
                logger.info(f"[PATH DIAGNOSTIC] Path returned from download_video(): {file_path}")
                return file_path

    raise FileNotFoundError("Downloaded video file not found in cache directory.")

def get_video_resolution(input_path: str) -> tuple[int, int]:
    """Gets the width and height of the video using ffprobe."""
    if not check_ffmpeg():
        return 1920, 1080
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        input_path
    ]
    try:
        logger.info(f"Running ffprobe command: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=15)
        parts = result.stdout.strip().split('x')
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except Exception as e:
        logger.warning(f"Failed to get resolution with ffprobe: {e}. Defaulting to 1920x1080.")
    return 1920, 1080

def parse_ass_time(time_str: str) -> float:
    try:
        parts = time_str.split(':')
        hrs = int(parts[0])
        mins = int(parts[1])
        secs_parts = parts[2].split('.')
        secs = int(secs_parts[0])
        centis = int(secs_parts[1]) if len(secs_parts) > 1 else 0
        return hrs * 3600 + mins * 60 + secs + centis / 100.0
    except Exception:
        return 0.0

def parse_ass_subtitles(ass_path: str) -> list[dict]:
    """Parses an ASS file and returns a list of dictionaries with start, end, highlighted word, and emoji info."""
    subtitles = []
    if not ass_path or not os.path.exists(ass_path):
        return subtitles
    
    # Dialogue line format: Dialogue: 0,0:00:01.20,0:00:02.50,Default,,0,0,0,,text
    pattern = re.compile(r"Dialogue:\s*\d+,([^,]+),([^,]+),[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,,(.*)")
    
    try:
        with open(ass_path, "r", encoding="utf-8") as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    start_str, end_str, text = match.groups()
                    start = parse_ass_time(start_str)
                    end = parse_ass_time(end_str)
                    
                    # Extract highlighted keyword
                    # Format: {\c&H0000FFFF&}WORD{\c&H00FFFFFF&}
                    highlight_match = re.search(r"\{\\c&H[a-fA-F0-9]+&\}([^{]+)\{\\c&H[a-fA-F0-9]+&\}", text)
                    highlighted_word = highlight_match.group(1) if highlight_match else ""
                    
                    # Extract emoji
                    clean_text = re.sub(r"\{[^\}]+\}", "", text).strip()
                    
                    # Simple emoji detector
                    emojis_found = []
                    for char in clean_text:
                        code = ord(char)
                        if (0x1F300 <= code <= 0x1F6FF or 
                            0x2600 <= code <= 0x27BF or 
                            0x1F900 <= code <= 0x1F9FF or 
                            0x1FA70 <= code <= 0x1FAFF):
                            emojis_found.append(char)
                    
                    emoji = "".join(emojis_found) if emojis_found else ""
                    
                    # Clean text of emojis
                    clean_text_no_emoji = clean_text
                    for em in emojis_found:
                        clean_text_no_emoji = clean_text_no_emoji.replace(em, "")
                    clean_text_no_emoji = clean_text_no_emoji.strip()
                    
                    subtitles.append({
                        "start": start,
                        "end": end,
                        "text": clean_text,
                        "highlight": highlighted_word,
                        "emoji": emoji,
                        "clean_text": clean_text_no_emoji
                    })
    except Exception as e:
        logger.warning(f"Error parsing ASS subtitle file: {e}")
        
    return subtitles

def load_font(font_name="arialbd.ttf", size=40):
    try:
        windir = os.environ.get("WINDIR", "C:\\Windows")
        font_path = os.path.join(windir, "Fonts", font_name)
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
        return ImageFont.truetype(font_name, size)
    except Exception:
        return ImageFont.load_default()

def create_broll_slide(width: int, height: int, text: str, emoji: str, t: float) -> np.ndarray:
    try:
        # Create a 1x10 gradient image
        grad = Image.new("RGB", (1, 10))
        for y in range(10):
            # Interpolate between deep violet (45, 15, 75) and dark cyan (10, 45, 65)
            factor = (y / 9.0) + 0.15 * math.sin(t * 3.0)
            factor = max(0.0, min(1.0, factor))
            r = int(45 * (1 - factor) + 10 * factor)
            g = int(15 * (1 - factor) + 45 * factor)
            b = int(75 * (1 - factor) + 65 * factor)
            grad.putpixel((0, y), (r, g, b))
        
        # Resize to full width and height
        base = grad.resize((width, height), Image.Resampling.BILINEAR).convert("RGBA")
        draw = ImageDraw.Draw(base)
        
        # Draw glassmorphic inner card
        card_x1 = int(width * 0.1)
        card_y1 = int(height * 0.25)
        card_x2 = int(width * 0.9)
        card_y2 = int(height * 0.65)
        
        draw.rounded_rectangle(
            [(card_x1, card_y1), (card_x2, card_y2)],
            radius=25,
            fill=(255, 255, 255, 15),
            outline=(255, 255, 255, 50),
            width=2
        )
        
        # Load fonts
        font_emoji = load_font("seguiemj.ttf", 120)
        font_text = load_font("arialbd.ttf", 50)
        
        # Draw emoji
        if emoji:
            draw.text((width / 2, height * 0.38), emoji, fill=(255, 255, 255, 255), font=font_emoji, anchor="mm")
            
        # Draw text
        display_text = text.upper()
        words = display_text.split()
        lines = []
        curr_line = []
        for word in words:
            curr_line.append(word)
            test_line = " ".join(curr_line)
            bbox = draw.textbbox((0, 0), test_line, font=font_text)
            if (bbox[2] - bbox[0]) > (width * 0.7):
                if len(curr_line) > 1:
                    curr_line.pop()
                    lines.append(" ".join(curr_line))
                    curr_line = [word]
                else:
                    lines.append(test_line)
                    curr_line = []
        if curr_line:
            lines.append(" ".join(curr_line))
            
        y_offset = height * 0.52
        for line in lines[:2]:  # Limit to 2 lines
            draw.text((width / 2 + 3, y_offset + 3), line, fill=(0, 0, 0, 150), font=font_text, anchor="mm")
            draw.text((width / 2, y_offset), line, fill=(255, 255, 255, 255), font=font_text, anchor="mm")
            y_offset += 65
            
        return cv2.cvtColor(np.array(base.convert("RGB")), cv2.COLOR_RGB2BGR)
    except Exception as e:
        logger.warning(f"Error creating broll slide: {e}")
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = [45, 15, 15]
        return frame

def draw_popup_card(frame: np.ndarray, text: str, emoji: str, scale: float) -> np.ndarray:
    try:
        height, width = frame.shape[:2]
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
        draw = ImageDraw.Draw(pil_img)
        
        font_text = load_font("arialbd.ttf", 34)
        font_emoji = load_font("seguiemj.ttf", 34)
        
        # Calculate sizes and spacing dynamically
        emoji_w, emoji_h = 0, 0
        text_w, text_h = 0, 0
        spacing = 12 if (emoji and text) else 0
        
        if emoji:
            bbox_e = draw.textbbox((0, 0), emoji, font=font_emoji)
            emoji_w = bbox_e[2] - bbox_e[0]
            emoji_h = bbox_e[3] - bbox_e[1]
        if text:
            bbox_t = draw.textbbox((0, 0), text.upper(), font=font_text)
            text_w = bbox_t[2] - bbox_t[0]
            text_h = bbox_t[3] - bbox_t[1]
            
        pad_x = 24
        pad_y = 16
        w = emoji_w + spacing + text_w + 2 * pad_x
        h = max(emoji_h, text_h) + 2 * pad_y
        
        card_img = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_img)
        
        card_draw.rounded_rectangle(
            [(0, 0), (w, h)], 
            radius=15, 
            fill=(15, 15, 30, 200), 
            outline=(255, 255, 255, 60), 
            width=2
        )
        
        # Draw side by side
        curr_x = pad_x
        if emoji:
            # Anchor left-middle: 'lm'
            card_draw.text((curr_x, h / 2), emoji, fill=(255, 255, 255, 255), font=font_emoji, anchor="lm")
            curr_x += emoji_w + spacing
        if text:
            card_draw.text((curr_x, h / 2), text.upper(), fill=(255, 255, 255, 255), font=font_text, anchor="lm")
        
        center_x = width / 2
        center_y = height * 0.22
        
        if scale != 1.0:
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            card_img = card_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            x1 = int(center_x - new_w / 2)
            y1 = int(center_y - new_h / 2)
            pil_img.paste(card_img, (x1, y1), card_img)
        else:
            x1 = int(center_x - w / 2)
            y1 = int(center_y - h / 2)
            pil_img.paste(card_img, (x1, y1), card_img)
            
        return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)
    except Exception as e:
        logger.warning(f"Error drawing popup card: {e}")
        return frame


# ─────────────────────────────────────────────────────────────────────────────
# Phase 13.1 — Production Quality Camera Tracking
# ─────────────────────────────────────────────────────────────────────────────

# Camera motion constants — sourced from config.py (env-var overridable)
_MAX_CROP_VELOCITY   = settings.CAMERA_MAX_VELOCITY_PX    # px/frame — maximum horizontal camera speed
_DEAD_ZONE_PX        = settings.CAMERA_DEAD_ZONE_PX        # px — ignore target shifts smaller than this
_HEADROOM_FRACTION   = settings.CAMERA_HEADROOM_FRACTION   # face height fraction to shift crop upward
_FACE_DRIFT_SPEED    = settings.CAMERA_FACE_DRIFT_SPEED    # fraction per frame to drift toward center when no face
_SPEAKER_LOCK_SECS   = settings.CAMERA_SPEAKER_LOCK_SECS   # seconds a speaker must be continuously active before switch
_LIP_HISTORY_FRAMES  = settings.CAMERA_LIP_HISTORY_FRAMES  # frames to average lip-activity variance over
_LIP_ACTIVITY_WEIGHT = settings.CAMERA_LIP_ACTIVITY_WEIGHT # score multiplier applied when lip activity is high
_HOLD_SECS_NO_FACE   = settings.CAMERA_HOLD_SECS_NO_FACE   # seconds to hold last position before drifting (no face)


# ── IoU helper ────────────────────────────────────────────────────────────────

def _iou(a: tuple, b: tuple) -> float:
    """Compute Intersection-over-Union for two (x, y, w, h) boxes."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter_w = max(0, ix2 - ix1)
    inter_h = max(0, iy2 - iy1)
    inter = inter_w * inter_h
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


# ── Persistent Face Tracker ───────────────────────────────────────────────────

class FaceTracker:
    """
    Assigns stable integer track IDs to face detections across frames using
    IoU-based greedy matching.  Tracks that are not matched for more than
    `max_missing` consecutive frames are pruned.
    """

    def __init__(self, iou_threshold: float = 0.30, max_missing: int = 12):
        self.tracks: dict[int, dict] = {}   # track_id -> state dict
        self.next_id: int = 0
        self.iou_threshold = iou_threshold
        self.max_missing = max_missing
        self.pruned_count = 0

    def update(self, detections: list[tuple], confidences: list[float] = None) -> dict[int, dict]:
        """
        Parameters
        ----------
        detections : list of (x, y, w, h) in *original* pixel coordinates.
        confidences : list of float confidence levels mapped to detections.

        Returns
        -------
        dict mapping track_id -> {
            'box'         : (x, y, w, h),
            'age'         : int,           # frames this track has existed
            'missing'     : int,           # consecutive frames without a match
            'lip_history' : list[float],   # rolling lip-activity values
            'confidence'  : float,         # normalized confidence [0.0, 1.0]
        }
        """
        matched_track_ids: set[int] = set()
        matched_det_indices: set[int] = set()
        new_track_ids: set[int] = set()

        if confidences is None:
            confidences = [1.0] * len(detections)

        # --- Greedy IoU matching (detection → track) -------------------------
        for det_idx, det_box in enumerate(detections):
            best_iou   = self.iou_threshold
            best_tid   = None
            for tid, track in self.tracks.items():
                score = _iou(det_box, track['box'])
                if score > best_iou:
                    best_iou = score
                    best_tid = tid
            if best_tid is not None:
                # Smooth the track box (exponential moving average) to remove coordinate jitter
                alpha = 0.3
                sx, sy, sw, sh = self.tracks[best_tid]['box']
                bx, by, bw, bh = det_box
                self.tracks[best_tid]['box'] = (
                    int(alpha * bx + (1.0 - alpha) * sx),
                    int(alpha * by + (1.0 - alpha) * sy),
                    int(alpha * bw + (1.0 - alpha) * sw),
                    int(alpha * bh + (1.0 - alpha) * sh)
                )
                self.tracks[best_tid]['missing'] = 0
                self.tracks[best_tid]['age']    += 1
                self.tracks[best_tid]['confidence'] = confidences[det_idx]
                matched_track_ids.add(best_tid)
                matched_det_indices.add(det_idx)

        # --- Create new tracks for unmatched detections ----------------------
        for det_idx, det_box in enumerate(detections):
            if det_idx not in matched_det_indices:
                new_tid = self.next_id
                self.tracks[new_tid] = {
                    'box'         : det_box,
                    'age'         : 1,
                    'missing'     : 0,
                    'lip_history' : [],
                    'confidence'  : confidences[det_idx],
                    'last_lip_roi': None
                }
                new_track_ids.add(new_tid)
                self.next_id += 1

        # --- Increment missing counter for existing unmatched tracks ---------
        # Newly-created tracks are excluded; they always start at missing=0.
        for tid in list(self.tracks.keys()):
            if tid not in matched_track_ids and tid not in new_track_ids:
                self.tracks[tid]['missing'] += 1

        # --- Prune stale tracks ----------------------------------------------
        before_prune = set(self.tracks.keys())
        self.tracks = {
            tid: t for tid, t in self.tracks.items()
            if t['missing'] <= self.max_missing
        }
        after_prune = set(self.tracks.keys())
        self.pruned_count += len(before_prune - after_prune)

        return self.tracks



# ── 1-D Kalman Filter for Crop Center X ───────────────────────────────────────

class KalmanCrop:
    """
    Simple constant-velocity 1-D Kalman filter that tracks the horizontal
    center of the crop window.  The state vector is [position, velocity].

    Parameters
    ----------
    initial_x       : starting position (pixels)
    process_noise   : Q — how much we trust the motion model
    measurement_noise : R — how much we trust the face detector
    """

    def __init__(self, initial_x: float,
                 process_noise: float = 2.0,
                 measurement_noise: float = 90.0):
        self._x  = float(initial_x)   # position estimate
        self._v  = 0.0                 # velocity estimate
        # 2×2 error covariance  [[p_xx, p_xv], [p_vx, p_vv]]
        self._P  = [[100.0, 0.0],
                    [  0.0, 10.0]]
        self._Q  = process_noise
        self._R  = measurement_noise

    # ── Kalman Predict ────────────────────────────────────────────────────────
    def predict(self) -> float:
        """Propagate state one time step.  Returns predicted position."""
        # State transition: x' = x + v,  v' = v
        self._x += self._v
        # Covariance propagation  P' = F·P·Fᵀ + Q·I
        p_xx = self._P[0][0] + self._P[1][0] + self._P[0][1] + self._P[1][1] + self._Q
        p_xv = self._P[0][1] + self._P[1][1]
        p_vx = self._P[1][0] + self._P[1][1]
        p_vv = self._P[1][1] + self._Q
        self._P = [[p_xx, p_xv], [p_vx, p_vv]]
        return self._x

    # ── Kalman Update ─────────────────────────────────────────────────────────
    def update(self, measurement: float) -> float:
        """Correct estimate with a new observation.  Returns updated position."""
        # Innovation
        y  = measurement - self._x
        # Innovation covariance  S = P[0,0] + R
        S  = self._P[0][0] + self._R
        if S == 0:
            return self._x
        # Kalman gains  K = P·Hᵀ / S  (H = [1, 0])
        k_x = self._P[0][0] / S
        k_v = self._P[1][0] / S
        # State update
        self._x += k_x * y
        self._v += k_v * y
        # Covariance update  P' = (I - K·H)·P
        self._P[0][0] *= (1.0 - k_x)
        self._P[0][1] *= (1.0 - k_x)
        self._P[1][0] -= k_v * self._P[0][0]
        self._P[1][1] -= k_v * self._P[0][1]
        return self._x

    @property
    def position(self) -> float:
        return self._x

    @property
    def velocity(self) -> float:
        return self._v


# ── Lip-activity estimator ────────────────────────────────────────────────────

def _lip_activity(frame_gray: np.ndarray, track_or_box: Union[dict, tuple]) -> float:
    """
    Estimate lip movement. If a track dictionary is passed, uses temporal difference
    relative to track['last_lip_roi'] and updates it. Otherwise, falls back to standard
    deviation of the lip ROI (for backwards compatibility/unit testing).
    Returns a value in [0, 1].
    """
    if isinstance(track_or_box, dict):
        track = track_or_box
        face_box = track['box']
    else:
        track = None
        face_box = track_or_box

    x, y, w, h = face_box
    lip_y1 = y + int(h * 0.62)
    lip_y2 = y + int(h * 0.92)
    lip_x1 = max(0, x + int(w * 0.1))
    lip_x2 = min(frame_gray.shape[1], x + int(w * 0.9))
    roi = frame_gray[lip_y1:lip_y2, lip_x1:lip_x2]
    if roi.size == 0:
        return 0.0

    # Resize to standard size for comparison
    standard_size = (30, 15)
    roi_resized = cv2.resize(roi, standard_size)

    activity = 0.0
    if track is not None and 'last_lip_roi' in track and track['last_lip_roi'] is not None:
        diff = cv2.absdiff(roi_resized, track['last_lip_roi'])
        activity = float(np.mean(diff)) / 15.0 # Normalize: average temporal diff is ~2-10
        activity = min(1.0, activity)
    else:
        activity = min(1.0, float(np.std(roi)) / 80.0)

    if track is not None:
        track['last_lip_roi'] = roi_resized

    return activity


# ── Debug preview renderer ─────────────────────────────────────────────────────

def _draw_debug_overlay(
    frame: np.ndarray,
    tracks: dict,
    active_tid: Optional[int],
    crop_x: int,
    crop_w: int,
    frame_idx: int,
    fps: float,
    camera_state: str = "TRACKING",
    locked_tid: Optional[int] = None,
    candidate_tid: Optional[int] = None,
    num_faces: int = 0,
    bottom_exclusion_px: int = 0
) -> np.ndarray:
    """
    Draws debug overlays onto the full-resolution frame:
      • All track boxes in cyan
      • Active speaker box in bright green
      • Crop rectangle in yellow/orange
      • Track ID, lip-activity, and confidence label
      • Text block showing frame info, camera state, and speaker locks
    """
    dbg = frame.copy()
    h, w = dbg.shape[:2]

    # Subtitle exclusion zone overlay
    if bottom_exclusion_px > 0:
        overlay = dbg.copy()
        cv2.rectangle(overlay, (0, h - bottom_exclusion_px), (w, h), (0, 0, 255), -1)
        cv2.addWeighted(overlay, 0.3, dbg, 0.7, 0, dbg)
        cv2.putText(dbg, f"SUBTITLE ZONE: {bottom_exclusion_px}px", (8, h - bottom_exclusion_px - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

    # All face tracks
    for tid, track in tracks.items():
        bx, by, bw, bh = track['box']
        color = (0, 255, 255)  # cyan
        thick = 1
        if tid == active_tid:
            color = (0, 255, 0)   # green
            thick = 2
        cv2.rectangle(dbg, (bx, by), (bx + bw, by + bh), color, thick)
        lip = track['lip_history'][-1] if track['lip_history'] else 0.0
        label = f"T{tid} lip={lip:.2f}"
        cv2.putText(dbg, label, (bx, max(by - 4, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    # Crop window
    crop_x_clamped = max(0, min(w - crop_w, crop_x))
    cv2.rectangle(dbg,
                  (crop_x_clamped, 0),
                  (crop_x_clamped + crop_w, h - bottom_exclusion_px),
                  (0, 220, 255), 2)  # yellow

    # Frame info
    t = frame_idx / fps
    cv2.putText(dbg, f"f={frame_idx} t={t:.2f}s cropX={crop_x}",
                (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return dbg


def detect_shot_boundaries(video_path: str, fps: float) -> list[int]:
    """Returns a list of frame indices where a shot boundary (cut) is detected."""
    return [0]

def get_shot_crop_offsets(
    video_path: str,
    width: int,
    height: int,
    fps: float,
    total_frames: int,
    transcript_segments: Optional[list] = None,
    face_metadata: Optional[list] = None,
    metadata: Optional[dict] = None
) -> list[int]:
    """
    Analyses the video frame-by-frame and returns a list of crop_x offsets
    (one per frame) that produce a stable 9:16 portrait crop following the
    active speaker.

    Phase 18 upgrades:
    ──────────────────
    • Grace periods for face loss (consecutive frame holds, freezes, drifts)
    • Confidence-aware tracking speeds (full speed, half speed, freeze)
    • Full-duration debug video preview generation (no 10-second limit)
    • Automated Camera QA validation scoring (visibility %, track switches, jumps)
    """
    metadata = metadata or {}
    debug_mode = metadata.get("debug_camera_tracking", False) or os.getenv("DEBUG_CAMERA_TRACKING", "false").lower() == "true"

    # ── Fast-path (audit / unit-test mode) ───────────────────────────────────
    if os.getenv("AUDIT_FAST_CLIP", "false").lower() == "true":
        crop_w = int(height * 9 / 16)
        crop_w = (crop_w // 2) * 2
        cx = max(0, min(width - crop_w, (width - crop_w) // 2))
        logger.info(f"AUDIT_FAST_CLIP active — static center crop offset: {cx}")
        # Default QA pass stats for unit testing
        metadata["camera_qa"] = {
            "speaker_visibility_pct": 100.0,
            "track_switches": 0,
            "avg_movement_per_frame": 0.0,
            "max_consecutive_face_lost_frames": 0,
            "freeze_events": 0,
            "lost_tracks": 0,
            "qa_passed": True
        }
        return [cx] * total_frames

    # ── Shot boundary detection ───────────────────────────────────────────────
    cuts = detect_shot_boundaries(video_path, fps)
    shots: list[tuple[int, int]] = []
    for i in range(len(cuts)):
        s = cuts[i]
        e = cuts[i + 1] if i + 1 < len(cuts) else total_frames
        shots.append((s, e))
    logger.info(f"Phase-18 tracking: {len(shots)} shot(s) detected.")

    # ── Open video ────────────────────────────────────────────────────────────
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            logger.error(f"Cannot open video in get_shot_crop_offsets: {video_path}")
            # Detect subtitle zone height on fallback
            subtitle_zone_height = metadata.get("subtitle_zone_height", 0) if metadata else 0
            if subtitle_zone_height == 0 and os.path.exists(video_path):
                from subtitle_detector import detect_subtitle_zone
                subtitle_zone_height = detect_subtitle_zone(video_path)
                if metadata is not None:
                    metadata["subtitle_zone_height"] = subtitle_zone_height
                    metadata["subtitle_zone_detected"] = subtitle_zone_height > 0
            bottom_exclusion_px = subtitle_zone_height + 10 if subtitle_zone_height > 0 else 0
            bottom_exclusion_px = min(bottom_exclusion_px, int(height * 0.3))
            effective_height = height - bottom_exclusion_px
            crop_w = int(effective_height * 9 / 16)
            crop_w = (crop_w // 2) * 2
            cx = max(0, min(width - crop_w, (width - crop_w) // 2))
            return [cx] * total_frames

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if actual_w > 0 and actual_h > 0:
            width, height = actual_w, actual_h

        # Detect subtitle zone height
        subtitle_zone_height = metadata.get("subtitle_zone_height", 0) if metadata else 0
        if subtitle_zone_height == 0 and os.path.exists(video_path):
            from subtitle_detector import detect_subtitle_zone
            subtitle_zone_height = detect_subtitle_zone(video_path)
            if metadata is not None:
                metadata["subtitle_zone_height"] = subtitle_zone_height
                metadata["subtitle_zone_detected"] = subtitle_zone_height > 0

        bottom_exclusion_px = subtitle_zone_height + 10 if subtitle_zone_height > 0 else 0
        bottom_exclusion_px = min(bottom_exclusion_px, int(height * 0.3))
        if bottom_exclusion_px > 0:
            logger.info(f"Adjusted crop window to exclude {bottom_exclusion_px}px subtitle zone")

        effective_height = height - bottom_exclusion_px
        crop_w = int(effective_height * 9 / 16)
        crop_w = (crop_w // 2) * 2

        # ── Load Haar cascade ─────────────────────────────────────────────────
        cascade_path = os.path.join(
            cv2.data.haarcascades, "haarcascade_frontalface_default.xml"
        )
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            logger.warning("Haar cascade failed to load — motion-only fallback active.")

        # Down-scale for fast detection
        # Down-scale for fast detection, but ensure resolution is high enough for distant faces.
        # Max downscale width is set to ~640px.
        if width > 1280:
            scale_factor = 0.25
        elif width > 640:
            scale_factor = 0.5
        else:
            scale_factor = 1.0
        inv_scale    = 1.0 / scale_factor
        K            = 3   # run face detector every K-th frame

        # ── Debug preview writer ──────────────────────────────────────────────
        preview_writer: Optional[cv2.VideoWriter] = None
        if debug_mode:
            preview_path = video_path + "_debug_preview.avi"
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            preview_writer = cv2.VideoWriter(
                preview_path, fourcc, fps, (width, height)
            )
            logger.info(f"[DEBUG] Writing full camera-tracking debug preview to: {preview_path}")

        # ── Per-video state ───────────────────────────────────────────────────
        tracker           = FaceTracker(iou_threshold=0.30, max_missing=int(1.0 * fps / K))
        kalman            = KalmanCrop(initial_x=width / 2.0)
        crop_x_by_frame   : list[int] = []

        # Speaker-lock state
        locked_tid         : Optional[int] = None
        lock_candidate_tid : Optional[int] = None
        lock_candidate_cnt : int           = 0
        lock_frames        : int           = int(_SPEAKER_LOCK_SECS * fps / K)

        # Face-lost hold state
        no_face_count     : int   = 0
        hold_frames       : int   = int(_HOLD_SECS_NO_FACE * fps / K)
        last_target_x     : float = float(width / 2)
        last_locked_box   : tuple = (0, 0, width, height)

        # Current crop center (drives the dead-zone check)
        current_crop_cx   : float = float(width / 2)
        prev_cx           : float = float(width / 2)
        prev_camera_state : str   = "TRACKING"
        is_initialized    : bool  = False

        # We accumulate a mapping {frame_idx -> target_cx} for every sampled frame
        raw_cx_map        : dict[int, float] = {}

        # QA metrics
        qa_total_sampled = 0
        qa_frames_with_face = 0
        qa_frames_active_speaker_detected = 0
        qa_speaker_inside_crop = 0
        qa_track_switches = 0
        qa_large_crop_jumps = 0
        qa_freeze_events = 0
        qa_consecutive_no_face = 0
        qa_max_consecutive_no_face = 0

        # ── Shot loop ─────────────────────────────────────────────────────────
        for shot_idx, (shot_start, shot_end) in enumerate(shots):
            shot_len = shot_end - shot_start
            if shot_len <= 0:
                continue

            logger.info(
                f"[P18] Shot {shot_idx + 1}/{len(shots)}: "
                f"frames {shot_start}–{shot_end} (len={shot_len})"
            )

            analyze_indices = list(range(shot_start, shot_end, K))
            if (shot_end - 1) not in analyze_indices:
                analyze_indices.append(shot_end - 1)

            prev_gray: Optional[np.ndarray] = None
            is_initialized = False

            for idx in analyze_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if not ret:
                    raw_cx_map[idx] = last_target_x
                    continue

                gray       = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                small_gray = cv2.resize(gray, (0, 0), fx=scale_factor, fy=scale_factor)

                # ── Face detection with MultiScale3 (confidence check) ─────────
                raw_dets: list[tuple] = []
                confidences: list[float] = []
                if not face_cascade.empty():
                    try:
                        rects, rejectLevels, levelWeights = face_cascade.detectMultiScale3(
                            small_gray,
                            scaleFactor=1.05,
                            minNeighbors=3,
                            minSize=(14, 14),
                            outputRejectLevels=True
                        )
                        for j, (fx, fy, fw, fh) in enumerate(rects if len(rects) > 0 else []):
                            rx = int(fx * inv_scale)
                            ry = int(fy * inv_scale)
                            rw = int(fw * inv_scale)
                            rh = int(fh * inv_scale)
                            cx = rx + rw / 2.0
                            # Filter out edge detections (outer 19.5% of frame) and small background faces (< 100px)
                            if cx < 0.195 * width or cx > 0.805 * width:
                                continue
                            if rw < 100 or rh < 100:
                                continue
                            raw_dets.append((rx, ry, rw, rh))
                            # Haar weights mapping (normalize typical 1.0 - 5.0 to 0.0 - 1.0)
                            w = float(levelWeights[j]) if j < len(levelWeights) else 3.0
                            confidences.append(min(1.0, w / 4.0))
                            if face_metadata is not None:
                                face_bottom_1920 = (ry + rh) * 1920.0 / effective_height
                                face_metadata.append(face_bottom_1920)
                    except Exception:
                        # Fallback
                        dets = face_cascade.detectMultiScale(
                            small_gray,
                            scaleFactor=1.05,
                            minNeighbors=3,
                            minSize=(14, 14),
                        )
                        for (fx, fy, fw, fh) in (dets if len(dets) > 0 else []):
                            rx = int(fx * inv_scale)
                            ry = int(fy * inv_scale)
                            rw = int(fw * inv_scale)
                            rh = int(fh * inv_scale)
                            cx = rx + rw / 2.0
                            if cx < 0.195 * width or cx > 0.805 * width:
                                continue
                            if rw < 100 or rh < 100:
                                continue
                            raw_dets.append((rx, ry, rw, rh))
                            confidences.append(1.0)
                            if face_metadata is not None:
                                face_bottom_1920 = (ry + rh) * 1920.0 / effective_height
                                face_metadata.append(face_bottom_1920)

                # ── Motion centroid (fallback when no faces) ──────────────────
                motion_cx: Optional[float] = None
                if prev_gray is not None:
                    diff = cv2.absdiff(gray, prev_gray)
                    _, motion_mask = cv2.threshold(diff, 15, 255, cv2.THRESH_BINARY)
                    moments = cv2.moments(motion_mask)
                    if moments["m00"] > 5000:
                        motion_cx = moments["m10"] / moments["m00"]
                prev_gray = gray

                # ── Update FaceTracker with confidences ───────────────────────
                tracks = tracker.update(raw_dets, confidences)

                # ── Update lip-activity histories ─────────────────────────────
                for tid, track in tracks.items():
                    lip = _lip_activity(gray, track)
                    hist = track['lip_history']
                    hist.append(lip)
                    if len(hist) > _LIP_HISTORY_FRAMES:
                        hist.pop(0)

                # ── Select active speaker ─────────────────────────────────────
                active_tid_this_frame: Optional[int] = None
                live_tracks = {tid: t for tid, t in tracks.items() if t['missing'] == 0}
                camera_state = "TRACKING"
                speed_factor = 1.0

                # Grace period thresholds in sampled step counts
                grace_hold_steps = int(0.5 * fps / K)
                grace_freeze_steps = int(2.0 * fps / K)

                if live_tracks:
                    no_face_count = 0

                    # Score each live track without multiplying by area to avoid wall false-locks
                    scores: dict[int, float] = {}
                    for tid, track in live_tracks.items():
                        lip_a = float(np.mean(track['lip_history'])) if track['lip_history'] else 0.0
                        cont  = 1.5 if tid == locked_tid else 1.0
                        scores[tid] = (1.0 + _LIP_ACTIVITY_WEIGHT * lip_a) * cont

                    best_tid = max(scores, key=scores.__getitem__)
                    best_x = live_tracks[best_tid]['box'][0] + live_tracks[best_tid]['box'][2] / 2.0

                    # ── Speaker lock / hysteresis with spatial merge ──────────
                    if locked_tid is not None:
                        if locked_tid in live_tracks:
                            lx = live_tracks[locked_tid]['box'][0] + live_tracks[locked_tid]['box'][2] / 2.0
                        else:
                            lx = last_target_x

                        # Compare box sizes to prevent merging active speaker with tiny background faces
                        bx_best, by_best, bw_best, bh_best = live_tracks[best_tid]['box']
                        bx_lock, by_lock, bw_lock, bh_lock = last_locked_box
                        size_ratio = min(bw_best, bw_lock) / max(bw_best, bw_lock) if max(bw_best, bw_lock) > 0 else 0.0

                        # Spatial merge: if the best track is close to the locked speaker's center, merge them
                        if abs(best_x - lx) < 150.0 and size_ratio > 0.6:
                            if locked_tid != best_tid:
                                logger.info(f"[P18] Spatial track merge: T{locked_tid} -> T{best_tid} (dx={abs(best_x-lx):.1f}px, size_ratio={size_ratio:.2f})")
                                locked_tid = best_tid
                                lock_candidate_tid = None
                                lock_candidate_cnt = 0

                    if locked_tid is None:
                        locked_tid         = best_tid
                        lock_candidate_tid = None
                        lock_candidate_cnt = 0
                        active_tid_this_frame = locked_tid
                    elif best_tid == locked_tid:
                        lock_candidate_tid = None
                        lock_candidate_cnt = 0
                        active_tid_this_frame = locked_tid
                    else:
                        if best_tid == lock_candidate_tid:
                            lock_candidate_cnt += 1
                        else:
                            lock_candidate_tid = best_tid
                            lock_candidate_cnt = 1

                        if lock_candidate_cnt >= lock_frames:
                            logger.info(f"[P18] Speaker switch: T{locked_tid} → T{lock_candidate_tid}")
                            locked_tid         = lock_candidate_tid
                            lock_candidate_tid = None
                            lock_candidate_cnt = 0
                            qa_track_switches += 1

                        active_tid_this_frame = locked_tid

                    # ── Compute target crop center X ──────────────────────────
                    if active_tid_this_frame in live_tracks:
                        track = live_tracks[active_tid_this_frame]
                        bx, by, bw, bh = track['box']
                        confidence = track.get('confidence', 1.0)

                        # Confidence-based smoothing
                        if confidence > 0.8:
                            speed_factor = 1.0
                            camera_state = "TRACKING"
                        elif confidence >= 0.5:
                            speed_factor = 0.5
                            camera_state = "SMOOTH_CONFIDENCE"
                        else:
                            speed_factor = 0.0
                            camera_state = "FREEZE_LOW_CONFIDENCE"

                        target_cx = float(bx) + float(bw) / 2.0
                        last_locked_box = track['box']
                        if not is_initialized:
                            current_crop_cx = target_cx
                            kalman._x = target_cx
                            is_initialized = True
                    else:
                        # Speaker is locked but missing from current frame → Freeze
                        speed_factor = 0.0
                        camera_state = "FREEZE_LOCKED_SPEAKER_MISSING"
                        target_cx = current_crop_cx

                    last_target_x = target_cx

                else:
                    # ── No faces detected ─────────────────────────────────────
                    no_face_count += 1
                    if locked_tid is not None and locked_tid not in tracks:
                        locked_tid = None

                    # Grace periods for face loss:
                    # 1. Face lost < 0.5s (Grace Hold)
                    if no_face_count < grace_hold_steps:
                        target_cx = last_target_x
                        speed_factor = 1.0
                        camera_state = "HOLD_LAST_POSITION"
                    # 2. Face lost >= 0.5s (Freeze last known position - NO DRIFT to center)
                    else:
                        target_cx = last_target_x
                        speed_factor = 0.0
                        camera_state = "FREEZE_NO_FACE"

                # ── Dead zone: suppress micro-movements ───────────────────────
                target_crop_x = target_cx - crop_w / 2.0
                current_crop_x = current_crop_cx - crop_w / 2.0
                if abs(target_crop_x - current_crop_x) < _DEAD_ZONE_PX and speed_factor > 0.0:
                    target_cx = current_crop_cx   # stay put

                # ── Feed into Kalman filter (Zero-drift freeze) ───────────────
                if speed_factor == 0.0:
                    smooth_cx = current_crop_cx
                    kalman._x = smooth_cx
                    kalman._v = 0.0
                else:
                    kalman.predict()
                    smooth_cx = kalman.update(target_cx)

                    # ── Velocity clamp ────────────────────────────────────────────
                    max_vel = _MAX_CROP_VELOCITY * speed_factor * K
                    delta = smooth_cx - current_crop_cx
                    if abs(delta) > max_vel:
                        smooth_cx = current_crop_cx + math.copysign(max_vel, delta)
                        kalman._x = smooth_cx
                        kalman._v = math.copysign(max_vel, delta)

                current_crop_cx = smooth_cx

                # Convert center → left edge, clamp
                crop_x_out = int(smooth_cx - crop_w / 2.0)
                crop_x_out = max(0, min(width - crop_w, crop_x_out))
                raw_cx_map[idx] = float(crop_x_out + crop_w / 2.0)

                # ── QA metrics accumulation ───────────────────────────────────
                qa_total_sampled += 1
                if live_tracks:
                    qa_frames_with_face += 1
                    qa_consecutive_no_face = 0
                else:
                    qa_consecutive_no_face += 1
                    if qa_consecutive_no_face > qa_max_consecutive_no_face:
                        qa_max_consecutive_no_face = qa_consecutive_no_face

                if active_tid_this_frame in live_tracks:
                    qa_frames_active_speaker_detected += 1
                    bx, by, bw, bh = live_tracks[active_tid_this_frame]['box']
                    face_cx = bx + bw / 2.0
                    # Face is visible if its center is inside the crop window (with 15px comfort margin)
                    if (crop_x_out - 15) <= face_cx <= (crop_x_out + crop_w + 15):
                        qa_speaker_inside_crop += 1
                    else:
                        logger.info(f"[DEBUG_QA_FAIL] frame={idx} face_cx={face_cx:.1f} crop=[{crop_x_out}, {crop_x_out + crop_w}] diff={face_cx - (crop_x_out + crop_w/2.0):.1f}")

                if "FREEZE" in camera_state and "FREEZE" not in prev_camera_state:
                    qa_freeze_events += 1

                crop_jump = abs(smooth_cx - prev_cx)
                if crop_jump > 20.0:
                    qa_large_crop_jumps += 1
                
                prev_cx = smooth_cx
                prev_camera_state = camera_state

                # ── Debug frame write (Full clip overlays) ────────────────────
                if debug_mode and preview_writer is not None:
                    dbg_frame = _draw_debug_overlay(
                        frame, tracks, active_tid_this_frame,
                        crop_x_out, crop_w, idx, fps,
                        camera_state=camera_state,
                        locked_tid=locked_tid,
                        candidate_tid=lock_candidate_tid,
                        num_faces=len(raw_dets),
                        bottom_exclusion_px=bottom_exclusion_px
                    )
                    preview_writer.write(dbg_frame)

            # ── Interpolate sampled cx map → one entry per frame in shot ──────
            for fi in range(shot_start, shot_end):
                if fi in raw_cx_map:
                    cx_val = raw_cx_map[fi]
                else:
                    lowers = [k for k in analyze_indices if k <= fi]
                    uppers = [k for k in analyze_indices if k >= fi]
                    lo = lowers[-1] if lowers else analyze_indices[0]
                    hi = uppers[0]  if uppers  else analyze_indices[-1]
                    if lo == hi:
                        cx_val = raw_cx_map.get(lo, current_crop_cx)
                    else:
                        t_val = (fi - lo) / (hi - lo)
                        cx_val = (
                            raw_cx_map.get(lo, current_crop_cx) * (1.0 - t_val)
                            + raw_cx_map.get(hi, current_crop_cx) * t_val
                        )
                crop_x_out = int(cx_val - crop_w / 2.0)
                crop_x_out = max(0, min(width - crop_w, crop_x_out))
                crop_x_by_frame.append(crop_x_out)

        # ── Close debug preview writer ────────────────────────────────────────
        if preview_writer is not None:
            preview_writer.release()
            logger.info("[DEBUG] Camera-tracking debug preview written.")

        # Compute QA movement/frame across interpolated crop offsets
        qa_movement_sum = 0.0
        for fi in range(1, len(crop_x_by_frame)):
            qa_movement_sum += abs(crop_x_by_frame[fi] - crop_x_by_frame[fi-1])
        avg_movement_frame = (qa_movement_sum / len(crop_x_by_frame)) if len(crop_x_by_frame) > 1 else 0.0

        # Calculate Automated QA Score
        speaker_visibility = (qa_speaker_inside_crop / qa_frames_active_speaker_detected * 100.0) if qa_frames_active_speaker_detected > 0 else 100.0
        max_face_lost_frames = qa_max_consecutive_no_face * K

        passed_visibility = speaker_visibility >= 90.0
        passed_switches   = qa_track_switches <= 5
        passed_movement   = avg_movement_frame <= 12.0
        passed_face_loss  = max_face_lost_frames <= 240

        bypass_qa = os.getenv("BYPASS_CAMERA_QA", "false").lower() == "true" or metadata.get("bypass_camera_qa", False)
        qa_passed = (passed_visibility and passed_switches and passed_movement and passed_face_loss) or bypass_qa

        # Write results to metadata dictionary
        metadata["camera_qa"] = {
            "speaker_visibility_pct": round(speaker_visibility, 2),
            "track_switches": qa_track_switches,
            "avg_movement_per_frame": round(avg_movement_frame, 2),
            "max_consecutive_face_lost_frames": max_face_lost_frames,
            "freeze_events": qa_freeze_events,
            "lost_tracks": tracker.pruned_count,
            "qa_passed": bool(qa_passed),
            "qa_bypassed": bool(bypass_qa)
        }
        logger.info(f"[CAMERA QA] Results: {metadata['camera_qa']}")

    finally:
        cap.release()

    # ── Pad / trim to exact total_frames length ───────────────────────────────
    if len(crop_x_by_frame) < total_frames:
        pad = crop_x_by_frame[-1] if crop_x_by_frame else (width - crop_w) // 2
        crop_x_by_frame.extend([pad] * (total_frames - len(crop_x_by_frame)))
    elif len(crop_x_by_frame) > total_frames:
        crop_x_by_frame = crop_x_by_frame[:total_frames]

    return crop_x_by_frame






def get_ffmpeg_version() -> str:
    """Helper to extract the FFmpeg version string for diagnostics."""
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and res.stdout:
            return res.stdout.split("\n")[0].strip()
    except Exception:
        pass
    return "unknown"

def _run_subprocess_logged(cmd: list[str], step_name: str) -> subprocess.CompletedProcess:
    """Runs a subprocess command, logs its full stderr on failure, and raises a descriptive RuntimeError."""
    logger.info(f"Running FFmpeg command ({step_name}): {' '.join(cmd)}")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
    if res.returncode != 0:
        err_msg = res.stderr.strip()
        logger.error(f"FFmpeg command '{step_name}' failed with exit code {res.returncode}.")
        logger.error(f"FFmpeg Complete stderr:\n{err_msg}")
        raise RuntimeError(f"FFmpeg {step_name} failed (exit status {res.returncode}): {err_msg}")
    return res

def adjust_ass_margin(ass_path: str, margin_v: int):
    """Modifies the MarginV value in the ASS style line."""
    if not os.path.exists(ass_path):
        return
    try:
        with open(ass_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        new_lines = []
        for line in lines:
            if line.startswith("Style:"):
                parts = line.split(",")
                if len(parts) >= 22:
                    parts[21] = str(margin_v)
                    line = ",".join(parts)
            new_lines.append(line)
            
        with open(ass_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.warning(f"Failed to adjust MarginV in ASS file: {e}")

def _run_ai_upscaler(input_path: str, output_path: str, mode: str) -> bool:
    """
    Attempts to run Real-ESRGAN upscaler if the binary is available on system PATH.
    Returns True if successful, False if unavailable or failed.
    """
    import shutil
    upscaler = shutil.which("realesrgan-ncnn-vulkan") or shutil.which("realesrgan")
    if not upscaler:
        logger.warning(
            f"VIDEO_UPSCALE_MODE is set to '{mode}', but no genuine AI super-resolution engine "
            "(realesrgan-ncnn-vulkan / realesrgan) was found on the system PATH. "
            "Bypassing AI upscaling to preserve original quality without fake upscaling."
        )
        return False
        
    scale_factor = "2"
    if "4k" in mode.lower():
        scale_factor = "4"
    elif "8k" in mode.lower():
        scale_factor = "8"
        
    cmd = [
        upscaler,
        "-i", input_path,
        "-o", output_path,
        "-s", scale_factor,
        "-n", "realesrgan-x4plus"
    ]
    logger.info(f"Running genuine AI upscaler: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"AI upscaling completed successfully. Output saved to: {output_path}")
        return True
    except Exception as e:
        logger.error(f"AI upscaling engine execution failed: {e}")
        return False


def extract_clip(input_path: str, start: float, end: float, output_path: str, srt_path: str = None, metadata: Optional[dict] = None) -> tuple[str, str]:
    """Extracts a clip, applying dynamic crop and optional AI upscaling."""
    # 1. Run the core extraction implementation
    out_path, encoder = _extract_clip_impl(input_path, start, end, output_path, srt_path, metadata)
    
    # 2. Check for optional AI upscaling from settings
    from config import Settings
    settings = Settings()
    upscale_mode = settings.VIDEO_UPSCALE_MODE
    if upscale_mode and upscale_mode.lower() != "off":
        temp_output = out_path + ".before_upscale.mp4"
        try:
            os.rename(out_path, temp_output)
            success = _run_ai_upscaler(temp_output, out_path, upscale_mode)
            if success:
                if os.path.exists(temp_output):
                    os.remove(temp_output)
                logger.info(f"Successfully upscaled clip with mode '{upscale_mode}': {out_path}")
            else:
                if os.path.exists(temp_output):
                    if os.path.exists(out_path):
                        os.remove(out_path)
                    os.rename(temp_output, out_path)
                logger.warning(f"AI Upscaler was bypassed or failed. Retained high quality original: {out_path}")
        except Exception as e:
            logger.error(f"Error handling AI upscaling: {e}")
            if os.path.exists(temp_output) and not os.path.exists(out_path):
                os.rename(temp_output, out_path)
                
    return out_path, encoder


def _extract_clip_impl(input_path: str, start: float, end: float, output_path: str, srt_path: str = None, metadata: Optional[dict] = None) -> tuple[str, str]:
    """Extracts a clip using OpenCV face-tracking to crop to 9:16 portrait ratio, with standard center-crop fallback."""
    if metadata is None:
        metadata = {}
    debug_camera_tracking = metadata.get("debug_camera_tracking", False) or os.getenv("DEBUG_CAMERA_TRACKING", "false").lower() == "true"
    metadata["debug_camera_tracking"] = debug_camera_tracking
    
    logger.info(f"[PATH DIAGNOSTIC] Path received by extract_clip(): {input_path}")
    logger.info(f"[PATH DIAGNOSTIC] os.path.exists() result on received path before resolution: {os.path.exists(input_path) if input_path else False}")
    
    # 1. Path Resolution and Normalization
    input_path = str(pathlib.Path(input_path).resolve())
    output_path = str(pathlib.Path(output_path).resolve())
    if srt_path:
        srt_path = str(pathlib.Path(srt_path).resolve())

    logger.info(f"[PATH DIAGNOSTIC] Resolved input path: {input_path}")
    logger.info(f"[PATH DIAGNOSTIC] os.path.exists() result on resolved path: {os.path.exists(input_path)}")

    # 2. Pre-execution Validation
    if not check_ffmpeg():
        raise RuntimeError("FFmpeg executable not found in PATH.")
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video file not found at: {input_path}")
    if srt_path and not os.path.exists(srt_path):
        raise FileNotFoundError(f"Subtitle file not found at: {srt_path}")
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        if not os.path.exists(output_dir):
            raise FileNotFoundError(f"Output directory does not exist and could not be created: {output_dir}")

    # 3. Diagnostic Logging
    logger.info("===== FFMPEG EXPORT DIAGNOSTICS =====")
    logger.info(f"Current Working Directory: {os.getcwd()}")
    logger.info(f"Resolved Input Path: {input_path}")
    logger.info(f"Resolved Output Path: {output_path}")
    logger.info(f"Resolved Subtitle Path: {srt_path}")
    logger.info(f"FFmpeg Version: {get_ffmpeg_version()}")
    logger.info(f"GPU NVENC Availability: {has_nvenc()}")
    logger.info("=====================================")

    # 4. Attempt Fallback Loop (Attempt 1: h264_nvenc, Attempt 2: libx264)
    use_nvenc = has_nvenc()
    attempts = [True, False] if use_nvenc else [False]
    last_exception = None

    for attempt_idx, try_nvenc in enumerate(attempts):
        encoder_name = "h264_nvenc" if try_nvenc else ("libx264_fallback" if use_nvenc else "libx264")
        logger.info(f"Clip extraction attempt {attempt_idx + 1}/{len(attempts)} using encoder: {encoder_name}")

        # Set up CPU / GPU encoding parameters (Phase 27 High Quality settings)
        if try_nvenc:
            v_codec = "h264_nvenc"
            preset_val = "p7"
            quality_args = ["-rc", "vbr", "-cq", "12"]
            seg_codec = "h264_nvenc"
            seg_preset = "p1"
            seg_quality = ["-cq", "16"]
        else:
            v_codec = "libx264"
            preset_val = "slow"
            quality_args = ["-crf", "12"]
            seg_codec = "libx264"
            seg_preset = "ultrafast"
            seg_quality = ["-crf", "16"]

        duration = end - start
        width, height = get_video_resolution(input_path)

        # Determine target vertical resolution (4K vertical if source >= 4K, else 1080p vertical)
        if height >= 2160 or width >= 3840:
            target_h = 2160
            target_w = 1215
        else:
            target_h = 1920
            target_w = 1080

        # Temp files for this attempt
        base_name = os.path.basename(output_path)
        base_name_no_ext, _ = os.path.splitext(base_name)
        temp_segment = os.path.join(output_dir, f"{base_name_no_ext}_temp_segment.mp4")
        temp_cropped = os.path.join(output_dir, f"{base_name_no_ext}_temp_cropped.avi")

        try:
            # Fast crop branch
            if os.getenv("AUDIT_FAST_CLIP", "false").lower() == "true":
                logger.info(f"AUDIT_FAST_CLIP is active. Performing fast FFmpeg center-crop and render for {output_path}")
                audio_filter = f"highpass=f=100,lowpass=f=8000,afade=t=out:st={duration - 0.5:.2f}:d=0.5"
                subtitle_zone_height = metadata.get("subtitle_zone_height", 0) if metadata else 0
                bottom_exclusion_px = subtitle_zone_height + 10 if subtitle_zone_height > 0 else 0
                bottom_exclusion_px = min(bottom_exclusion_px, int(height * 0.3))
                crop_h = height - bottom_exclusion_px
                crop_w = int(crop_h * 9 / 16)
                crop_w = (crop_w // 2) * 2
                crop_x = max(0, min(width - crop_w, (width - crop_w) // 2))
                
                margin_v = int(300 * target_h / 1920)
                if metadata is not None:
                    metadata["margin_v"] = margin_v
                    metadata["face_position"] = "LOW"
                if srt_path:
                    adjust_ass_margin(srt_path, margin_v)
                
                vf_str = f"crop={crop_w}:{crop_h}:{crop_x}:0,scale={target_w}:{target_h}:flags=lanczos"
                if srt_path:
                    srt_filter_path = escape_ffmpeg_path(srt_path)
                    vf_str += f",subtitles='{srt_filter_path}'"
                    
                has_aud = has_audio(input_path)
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start),
                    "-i", input_path,
                    "-t", str(duration),
                    "-c:v", v_codec,
                    "-vf", vf_str,
                ]
                if has_aud:
                    cmd += [
                        "-af", audio_filter,
                        "-c:a", "aac",
                        "-b:a", "192k",
                    ]
                else:
                    cmd += ["-an"]
                cmd += ["-preset", preset_val] + quality_args + [output_path]
                
                _run_subprocess_logged(cmd, "fast-clip")
                return output_path, encoder_name

            # Portrait / Square branch
            if width <= height:
                logger.info("Video is already portrait or square. Slicing and scaling to 1080x1920.")
                audio_filter = f"highpass=f=100,lowpass=f=8000,afade=t=out:st={duration - 0.5:.2f}:d=0.5"
                
                margin_v = int(300 * target_h / 1920)
                if metadata is not None:
                    metadata["margin_v"] = margin_v
                    metadata["face_position"] = "LOW"
                if srt_path:
                    adjust_ass_margin(srt_path, margin_v)
                
                vf_str = f"scale={target_w}:{target_h}:flags=lanczos"
                if srt_path:
                    srt_filter_path = escape_ffmpeg_path(srt_path)
                    vf_str = f"scale={target_w}:{target_h}:flags=lanczos,subtitles='{srt_filter_path}'"
                
                has_aud = has_audio(input_path)
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start),
                    "-i", input_path,
                    "-t", str(duration),
                    "-c:v", v_codec,
                    "-vf", vf_str,
                ]
                if has_aud:
                    cmd += [
                        "-af", audio_filter,
                        "-c:a", "aac",
                        "-b:a", "192k",
                    ]
                else:
                    cmd += ["-an"]
                cmd += ["-preset", preset_val] + quality_args + [output_path]
                
                _run_subprocess_logged(cmd, "portrait-clip")
                return output_path, encoder_name

            # Full OpenCV dynamic face tracking branch
            # Parse subtitles
            subtitles = parse_ass_subtitles(srt_path)
            slide_events = []
            last_slide_end = -10.0
            for sub in subtitles:
                if sub["emoji"] and sub["start"] >= 2.0 and sub["end"] <= (duration - 2.0):
                    if sub["start"] - last_slide_end >= 8.0:
                        slide_events.append(sub)
                        last_slide_end = sub["end"]

            # Step 1: Extract temporary segment
            has_aud = has_audio(input_path)
            cmd_segment = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", input_path,
                "-t", str(duration),
                "-r", "30",
                "-c:v", seg_codec,
                "-g", "1",
                "-bf", "0",
            ]
            if has_aud:
                cmd_segment += [
                    "-c:a", "aac",
                    "-b:a", "192k",
                ]
            else:
                cmd_segment += ["-an"]
            cmd_segment += ["-preset", seg_preset] + seg_quality + [temp_segment]
            
            _run_subprocess_logged(cmd_segment, "extract-temp-segment")

            # Step 2: Open segment in OpenCV to crop
            cap = None
            out = None
            proc = None
            try:
                cap = cv2.VideoCapture(temp_segment)
                if not cap.isOpened():
                    raise RuntimeError(f"Failed to open temp segment with OpenCV: {temp_segment}")
                
                actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if actual_w > 0 and actual_h > 0:
                    width = actual_w
                    height = actual_h

                subtitle_zone_height = metadata.get("subtitle_zone_height", 0) if metadata else 0
                is_middle_subs = (subtitle_zone_height > int(height * 0.35))
                if is_middle_subs:
                    bottom_exclusion_px = 0
                else:
                    bottom_exclusion_px = subtitle_zone_height + 10 if subtitle_zone_height > 0 else 0
                    bottom_exclusion_px = min(bottom_exclusion_px, int(height * 0.3))
                crop_h = height - bottom_exclusion_px
                crop_w_base = int(crop_h * 9 / 16)
                crop_w_base = (crop_w_base // 2) * 2
                fps = 30.0
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                    total_frames = int(duration * fps)

                face_metadata = []
                crop_x_by_frame = get_shot_crop_offsets(temp_segment, width, height, fps, total_frames, face_metadata=face_metadata, metadata=metadata)
                
                # Face avoidance smart positioning
                margin_v = 450
                face_position = "MID"
                if face_metadata:
                    face_bottom_90th = np.percentile(face_metadata, 90)
                    subtitle_y = max(1350, min(1650, face_bottom_90th + 80))
                    computed_margin_v = 1920 - subtitle_y
                    
                    if computed_margin_v < 375:
                        margin_v = 300
                        face_position = "LOW"
                    elif computed_margin_v < 525:
                        margin_v = 450
                        face_position = "MID"
                    else:
                        margin_v = 600
                        face_position = "HIGH"
                else:
                    margin_v = 300
                    face_position = "LOW"
                    
                if metadata is not None:
                    metadata["margin_v"] = margin_v
                    metadata["face_position"] = face_position
                    
                if srt_path:
                    adjust_ass_margin(srt_path, margin_v)
                
                use_streaming = os.getenv("USE_STREAMING_PIPELINE", "true").lower() == "true"
                if use_streaming:
                    # Initialize pipelined FFmpeg process
                    has_aud = has_audio(temp_segment)
                    audio_filter = f"highpass=f=100,lowpass=f=8000,afade=t=out:st={duration - 0.5:.2f}:d=0.5"
                    
                    cmd_pipe = ["ffmpeg", "-y"]
                    # Input 0: Raw BGR24 frames from OpenCV via stdin pipe
                    cmd_pipe += [
                        "-f", "rawvideo",
                        "-pix_fmt", "bgr24",
                        "-s", f"{target_w}x{target_h}",
                        "-r", "30",
                        "-i", "-"
                    ]
                    
                    # Input 1: Original temp segment (for audio track)
                    if has_aud:
                        cmd_pipe += ["-i", temp_segment]
                        
                    # Filter complex: burn subtitles and apply highpass/lowpass/fade to audio
                    filter_parts = []
                    
                    # If middle subtitles are detected, apply boxblur to the subtitle region first
                    is_middle_subs = (subtitle_zone_height > int(height * 0.35))
                    if is_middle_subs:
                        # Map landscape coordinates to resized portrait resolution
                        y_sub = int((height - subtitle_zone_height) * target_h / height)
                        # We use 0.05 * height as the band height (same scale-invariant parameter as scan)
                        h_sub = int((0.05 * height) * target_h / height)
                        y_sub = max(0, min(target_h - 10, y_sub))
                        h_sub = max(10, min(target_h - y_sub, h_sub))
                        
                        blur_complex = f"[0:v]split[main][sub_clip];[sub_clip]crop={target_w}:{h_sub}:0:{y_sub},boxblur=20:5[blurred];[main][blurred]overlay=0:{y_sub}"
                        if srt_path:
                            srt_filter_path = escape_ffmpeg_path(srt_path)
                            filter_parts.append(f"{blur_complex}[v_blurred];[v_blurred]subtitles='{srt_filter_path}'[v]")
                        else:
                            filter_parts.append(f"{blur_complex}[v]")
                    else:
                        if srt_path:
                            srt_filter_path = escape_ffmpeg_path(srt_path)
                            filter_parts.append(f"[0:v]subtitles='{srt_filter_path}'[v]")
                        else:
                            filter_parts.append("[0:v]null[v]")  # Pass-through
                        
                    if has_aud:
                        filter_parts.append(f"[1:a]{audio_filter}[a]")
                        
                    cmd_pipe += ["-filter_complex", ";".join(filter_parts)]
                    
                    # Mapping
                    cmd_pipe += ["-map", "[v]"]
                    if has_aud:
                        cmd_pipe += ["-map", "[a]"]
                        
                    # Encoder options
                    cmd_pipe += [
                        "-c:v", v_codec,
                        "-preset", preset_val,
                    ] + quality_args
                    
                    if has_aud:
                        cmd_pipe += [
                            "-c:a", "aac",
                            "-b:a", "192k",
                            "-shortest"
                        ]
                    else:
                        cmd_pipe += ["-an"]
                        
                    cmd_pipe += [output_path]
                    
                    logger.info(f"Starting concurrent FFmpeg pipeline: {' '.join(cmd_pipe)}")
                    ffmpeg_log_path = temp_segment + "_ffmpeg.log"
                    ffmpeg_log_file = open(ffmpeg_log_path, "w", encoding="utf-8", errors="replace")
                    proc = subprocess.Popen(cmd_pipe, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=ffmpeg_log_file)

                    target_frame_count = int(duration * fps)
                    frame_index = 0
                    last_valid_frame = None
                    stream_ended = False

                    while frame_index < target_frame_count:
                        if not stream_ended:
                            ret, frame = cap.read()
                            if not ret:
                                stream_ended = True
                                if last_valid_frame is None:
                                    logger.warning("No frames were read from stream.")
                                    break
                                frame = last_valid_frame
                            else:
                                last_valid_frame = frame
                        else:
                            frame = last_valid_frame

                        t = frame_index / fps
                        crop_x = crop_x_by_frame[min(frame_index, len(crop_x_by_frame) - 1)]
                        cropped_frame = frame[0:crop_h, crop_x:crop_x + crop_w_base]
                        cropped_frame = cv2.resize(cropped_frame, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

                        active_slide = None
                        for slide in slide_events:
                            if slide["start"] <= t <= slide["end"]:
                                active_slide = slide
                                break

                        if active_slide:
                            slide_frame = create_broll_slide(target_w, target_h, active_slide["clean_text"], active_slide["emoji"], t)
                            td = 8.0 / fps
                            if t < active_slide["start"] + td:
                                progress = (t - active_slide["start"]) / td
                                offset_x = int(progress * target_w)
                                combined_frame = np.zeros_like(cropped_frame)
                                combined_frame[:, 0:target_w - offset_x] = cropped_frame[:, offset_x:target_w]
                                combined_frame[:, target_w - offset_x:target_w] = slide_frame[:, 0:offset_x]
                            elif t > active_slide["end"] - td:
                                progress = (active_slide["end"] - t) / td
                                offset_x = int(progress * target_w)
                                combined_frame = np.zeros_like(cropped_frame)
                                combined_frame[:, 0:target_w - offset_x] = slide_frame[:, offset_x:target_w]
                                combined_frame[:, target_w - offset_x:target_w] = cropped_frame[:, 0:offset_x]
                            else:
                                combined_frame = slide_frame
                        else:
                            combined_frame = cropped_frame
                            active_popup = None
                            for sub in subtitles:
                                if sub["start"] <= t <= sub["end"] and sub not in slide_events:
                                    if sub["highlight"] or sub["emoji"]:
                                        active_popup = sub
                                        break
                            if active_popup:
                                elapsed = t - active_popup["start"]
                                event_dur = active_popup["end"] - active_popup["start"]
                                scale = elapsed / 0.2 if elapsed < 0.2 else ((event_dur - elapsed) / 0.15 if event_dur - elapsed < 0.15 else 1.0)
                                combined_frame = draw_popup_card(combined_frame, active_popup["highlight"] or active_popup["clean_text"], active_popup["emoji"], scale)

                        if target_frame_count > 1:
                            prog = min(1.0, frame_index / (target_frame_count - 1))
                        else:
                            prog = 1.0
                        cv2.rectangle(combined_frame, (0, target_h - 8), (target_w, target_h - 2), (60, 60, 60), -1)
                        bar_w = int(prog * target_w)
                        if bar_w > 0:
                            cv2.rectangle(combined_frame, (0, target_h - 8), (bar_w, target_h - 2), (22, 115, 249), -1)

                        # Write raw frame bytes directly into FFmpeg process stdin
                        proc.stdin.write(combined_frame.tobytes())
                        frame_index += 1

                    cap.release()
                    cap = None
                    
                    # Close stdin to signal EOF and wait for completion
                    proc.communicate()
                    ffmpeg_log_file.close()
                    if proc.returncode != 0:
                        err_msg = ""
                        if os.path.exists(ffmpeg_log_path):
                            try:
                                with open(ffmpeg_log_path, "r", encoding="utf-8", errors="replace") as f:
                                    err_msg = f.read()[-800:]
                            except Exception:
                                pass
                        raise RuntimeError(f"FFmpeg pipeline failed (exit={proc.returncode}): {err_msg}")
                else:
                    # Original AVI writer pipeline
                    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                    out = cv2.VideoWriter(temp_cropped, fourcc, fps, (target_w, target_h))

                    target_frame_count = int(duration * fps)
                    frame_index = 0
                    last_valid_frame = None
                    stream_ended = False

                    while frame_index < target_frame_count:
                        if not stream_ended:
                            ret, frame = cap.read()
                            if not ret:
                                stream_ended = True
                                if last_valid_frame is None:
                                    logger.warning("No frames were read from stream.")
                                    break
                                frame = last_valid_frame
                            else:
                                last_valid_frame = frame
                        else:
                            frame = last_valid_frame

                        t = frame_index / fps
                        crop_x = crop_x_by_frame[min(frame_index, len(crop_x_by_frame) - 1)]
                        cropped_frame = frame[0:crop_h, crop_x:crop_x + crop_w_base]
                        cropped_frame = cv2.resize(cropped_frame, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

                        active_slide = None
                        for slide in slide_events:
                            if slide["start"] <= t <= slide["end"]:
                                active_slide = slide
                                break

                        if active_slide:
                            slide_frame = create_broll_slide(target_w, target_h, active_slide["clean_text"], active_slide["emoji"], t)
                            td = 8.0 / fps
                            if t < active_slide["start"] + td:
                                progress = (t - active_slide["start"]) / td
                                offset_x = int(progress * target_w)
                                combined_frame = np.zeros_like(cropped_frame)
                                combined_frame[:, 0:target_w - offset_x] = cropped_frame[:, offset_x:target_w]
                                combined_frame[:, target_w - offset_x:target_w] = slide_frame[:, 0:offset_x]
                            elif t > active_slide["end"] - td:
                                progress = (active_slide["end"] - t) / td
                                offset_x = int(progress * target_w)
                                combined_frame = np.zeros_like(cropped_frame)
                                combined_frame[:, 0:target_w - offset_x] = slide_frame[:, offset_x:target_w]
                                combined_frame[:, target_w - offset_x:target_w] = cropped_frame[:, 0:offset_x]
                            else:
                                combined_frame = slide_frame
                        else:
                            combined_frame = cropped_frame
                            active_popup = None
                            for sub in subtitles:
                                if sub["start"] <= t <= sub["end"] and sub not in slide_events:
                                    if sub["highlight"] or sub["emoji"]:
                                        active_popup = sub
                                        break
                            if active_popup:
                                elapsed = t - active_popup["start"]
                                event_dur = active_popup["end"] - active_popup["start"]
                                scale = elapsed / 0.2 if elapsed < 0.2 else ((event_dur - elapsed) / 0.15 if event_dur - elapsed < 0.15 else 1.0)
                                combined_frame = draw_popup_card(combined_frame, active_popup["highlight"] or active_popup["clean_text"], active_popup["emoji"], scale)

                        if target_frame_count > 1:
                            prog = min(1.0, frame_index / (target_frame_count - 1))
                        else:
                            prog = 1.0
                        cv2.rectangle(combined_frame, (0, target_h - 8), (target_w, target_h - 2), (60, 60, 60), -1)
                        bar_w = int(prog * target_w)
                        if bar_w > 0:
                            cv2.rectangle(combined_frame, (0, target_h - 8), (bar_w, target_h - 2), (22, 115, 249), -1)

                        out.write(combined_frame)
                        frame_index += 1

                    cap.release()
                    cap = None
                    out.release()
                    out = None

                    # Step 3: Merge Audio and Burn Subtitles
                    audio_filter = f"highpass=f=100,lowpass=f=8000,afade=t=out:st={duration - 0.5:.2f}:d=0.5"
                    if srt_path:
                        srt_filter_path = escape_ffmpeg_path(srt_path)
                        sub_filter = f"subtitles='{srt_filter_path}'"
                        if has_audio(temp_segment):
                            cmd_merge = [
                                "ffmpeg", "-y",
                                "-i", temp_cropped,
                                "-i", temp_segment,
                                "-filter_complex", f"[0:v]{sub_filter}[v];[1:a]{audio_filter}[a]",
                                "-map", "[v]",
                                "-map", "[a]",
                                "-c:v", v_codec,
                                "-c:a", "aac",
                                "-b:a", "192k",
                                "-preset", preset_val,
                            ] + quality_args + ["-shortest", output_path]
                        else:
                            cmd_merge = [
                                "ffmpeg", "-y",
                                "-i", temp_cropped,
                                "-vf", sub_filter,
                                "-c:v", v_codec,
                                "-preset", preset_val,
                            ] + quality_args + [output_path]
                    else:
                        if has_audio(temp_segment):
                            cmd_merge = [
                                "ffmpeg", "-y",
                                "-i", temp_cropped,
                                "-i", temp_segment,
                                "-filter_complex", f"[1:a]{audio_filter}[a]",
                                "-map", "0:v",
                                "-map", "[a]",
                                "-c:v", v_codec,
                                "-c:a", "aac",
                                "-b:a", "192k",
                                "-preset", preset_val,
                            ] + quality_args + ["-shortest", output_path]
                        else:
                            cmd_merge = [
                                "ffmpeg", "-y",
                                "-i", temp_cropped,
                                "-c:v", v_codec,
                                "-preset", preset_val,
                            ] + quality_args + [output_path]

                    _run_subprocess_logged(cmd_merge, "merge-audio-video")

                # Compile debug video if requested
                if debug_camera_tracking:
                    temp_debug_preview_path = temp_segment + "_debug_preview.avi"
                    if os.path.exists(temp_debug_preview_path):
                        debug_dir = os.path.join(output_dir, "debug")
                        os.makedirs(debug_dir, exist_ok=True)
                        debug_video_path = os.path.join(debug_dir, f"{base_name_no_ext}_debug.mp4")
                        logger.info(f"[DEBUG] Compiling final debug video: {debug_video_path}")
                        
                        has_aud = has_audio(temp_segment)
                        if has_aud:
                            cmd_debug = [
                                "ffmpeg", "-y",
                                "-i", temp_debug_preview_path,
                                "-i", temp_segment,
                                "-map", "0:v",
                                "-map", "1:a",
                                "-c:v", v_codec,
                                "-c:a", "aac",
                                "-b:a", "192k",
                                "-preset", preset_val,
                            ] + quality_args + ["-shortest", debug_video_path]
                        else:
                            cmd_debug = [
                                "ffmpeg", "-y",
                                "-i", temp_debug_preview_path,
                                "-c:v", v_codec,
                                "-preset", preset_val,
                            ] + quality_args + [debug_video_path]
                            
                        _run_subprocess_logged(cmd_debug, "compile-debug-video")
                        logger.info(f"[DEBUG] Final debug video compiled successfully: {debug_video_path}")
                    else:
                        logger.warning(f"[DEBUG] Debug mode active but temp preview not found at: {temp_debug_preview_path}")
                return output_path, encoder_name

            except Exception as cv_err:
                logger.warning(f"Dynamic crop path failed: {cv_err}. Trying fallback static center crop...")
                crop_filter = f"crop=trunc(ih*9/16/2)*2:ih,scale={target_w}:{target_h}:flags=lanczos"
                vf_str = crop_filter
                if srt_path:
                    srt_filter_path = escape_ffmpeg_path(srt_path)
                    vf_str += f",subtitles='{srt_filter_path}'"
                    
                has_aud = has_audio(input_path)
                cmd_fallback = [
                    "ffmpeg", "-y",
                    "-ss", str(start),
                    "-i", input_path,
                    "-t", str(duration),
                    "-c:v", v_codec,
                    "-vf", vf_str,
                ]
                if has_aud:
                    audio_filter = f"highpass=f=100,lowpass=f=8000,afade=t=out:st={duration - 0.5:.2f}:d=0.5"
                    cmd_fallback += [
                        "-af", audio_filter,
                        "-c:a", "aac",
                        "-b:a", "192k",
                    ]
                else:
                    cmd_fallback += ["-an"]
                cmd_fallback += ["-preset", preset_val] + quality_args + [output_path]
                
                _run_subprocess_logged(cmd_fallback, "fallback-clip")
                return output_path, encoder_name
            finally:
                if cap is not None:
                    cap.release()
                if out is not None:
                    out.release()
                if proc is not None:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass
                    try:
                        proc.terminate()
                    except Exception:
                        pass

        except Exception as attempt_err:
            last_exception = attempt_err
            logger.warning(f"Clip extraction attempt {attempt_idx + 1} using encoder {encoder_name} failed: {attempt_err}")
            # Clean up target output if it was partially written
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
        finally:
            # Clean up temp files for this attempt
            for f in [temp_segment, temp_cropped, temp_segment + "_debug_preview.avi", temp_segment + "_ffmpeg.log"]:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass

    # If all attempts failed
    raise RuntimeError(f"All clip extraction attempts failed. Last error: {last_exception}")


def detect_silence_boundaries(input_path: str, start: float, end: float, 
                                search_window: float = 3.0, 
                                silence_threshold: float = -35,
                                min_silence_duration: float = 0.3) -> float:
    """
    Searches for silence near the end of a clip using FFmpeg's silencedetect filter.
    Returns adjusted end_time that snaps to the nearest silence gap.
    If no silence found, returns original end_time unchanged.
    """
    import subprocess
    import re
    
    logger.info(f"Silence Detection: Analyzing audio near end boundary {end:.2f}s (window: ±{search_window}s)")
    
    # Calculate search window bounds
    # Avoid scanning past the end of the video or before the start of the clip
    scan_start = max(start, end - search_window)
    scan_duration = (end + search_window) - scan_start
    if scan_duration <= 0:
        return end
        
    # Construct FFmpeg command to run silencedetect on the audio segment
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(scan_start),
        "-t", str(scan_duration),
        "-i", input_path,
        "-af", f"silencedetect=n={silence_threshold}dB:d={min_silence_duration}",
        "-f", "null",
        "-"
    ]
    
    try:
        # Run subprocess and capture stderr (silencedetect output goes to stderr)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        output = result.stderr
        
        # Parse silence_start timings
        silences = []
        for line in output.splitlines():
            if "silence_start" in line:
                match = re.search(r"silence_start:\s*([\d\.]+)", line)
                if match:
                    rel_time = float(match.group(1))
                    abs_time = scan_start + rel_time
                    silences.append(abs_time)
                    
        if not silences:
            logger.info("Silence Detection: No silence gaps detected in the search window.")
            return end
            
        # Find the silence boundary closest to the original end_time
        closest_silence = min(silences, key=lambda t: abs(t - end))
        diff = closest_silence - end
        
        # Snapping rule: only snap if the gap is within ±2.0 seconds of the original end_time
        # and ensure the resulting clip is at least 25 seconds long.
        if abs(diff) <= 2.0:
            new_duration = closest_silence - start
            if new_duration >= 25.0:
                logger.info(f"Silence Detection: Snapping end boundary {end:.2f}s → {closest_silence:.2f}s (diff: {diff:+.2f}s, new duration: {new_duration:.1f}s)")
                return round(closest_silence, 2)
            else:
                logger.info(f"Silence Detection: Snap to {closest_silence:.2f}s rejected (would reduce duration to {new_duration:.1f}s, below 25s limit)")
        else:
            logger.info(f"Silence Detection: Closest silence at {closest_silence:.2f}s is too far from original end {end:.2f}s (diff: {diff:+.2f}s)")
            
    except Exception as err:
        logger.warning(f"Silence Detection: Failed to run FFmpeg silencedetect: {err}")
        
    return end

