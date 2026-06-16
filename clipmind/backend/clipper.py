import os
import shutil
import subprocess
import logging
import yt_dlp
import cv2
import math
import re
from PIL import Image, ImageDraw, ImageFont
import numpy as np

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
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return len(result.stdout.strip()) > 0
    except Exception as e:
        logger.warning(f"Failed to check for audio: {e}. Assuming no audio.")
        return False

def download_video(url: str, download_dir: str, progress_callback=None) -> str:
    """Downloads the best available MP4 video using yt-dlp."""
    os.makedirs(download_dir, exist_ok=True)
    outtmpl = os.path.join(download_dir, 'full_video.%(ext)s')

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

    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        'merge_output_format': 'mp4',
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [ytdl_hook],
    }

    logger.info(f"Starting video download for URL: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    valid_exts = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
    for file in os.listdir(download_dir):
        if file.startswith("full_video."):
            _, ext = os.path.splitext(file)
            if ext.lower() in valid_exts:
                file_path = os.path.join(download_dir, file)
                logger.info(f"Downloaded video located at: {file_path}")
                return file_path

    raise FileNotFoundError("Downloaded video file not found in output directory.")

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
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
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


# Speed at which crop center drifts back to frame-center when face is lost
_FACE_DRIFT_SPEED = 0.05


def detect_shot_boundaries(video_path: str, fps: float) -> list[int]:
    """Detects frame indices where shot cuts occur in the video using grayscale difference."""
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            return [0]
            
        prev_gray = None
        frame_idx = 0
        diff_values = []
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small_gray = cv2.resize(gray, (0, 0), fx=0.1, fy=0.1)
            
            if prev_gray is not None:
                diff = cv2.absdiff(small_gray, prev_gray)
                mean_diff = np.mean(diff)
                diff_values.append((frame_idx, mean_diff))
            else:
                diff_values.append((frame_idx, 0.0))
                
            prev_gray = small_gray
            frame_idx += 1
    finally:
        cap.release()
    
    if not diff_values:
        return [0]
        
    diffs = [v[1] for v in diff_values]
    avg_diff = np.mean(diffs)
    std_diff = np.std(diffs)
    
    threshold = avg_diff + 5.0 * std_diff
    threshold = max(threshold, 15.0)
    
    detected_cuts = [0]
    for idx, mean_diff in diff_values:
        if mean_diff > threshold:
            if (idx - detected_cuts[-1]) > (fps * 1.5):
                detected_cuts.append(idx)
                
    return detected_cuts

def smooth_signal(data: list[float], window_size: int) -> list[float]:
    if not data:
        return []
    if len(data) <= window_size:
        window_size = max(1, len(data))
    
    half_w = window_size // 2
    padded = [data[0]] * half_w + data + [data[-1]] * half_w
    
    smoothed = []
    current_sum = sum(padded[:window_size])
    smoothed.append(current_sum / window_size)
    for i in range(len(data) - 1):
        current_sum = current_sum - padded[i] + padded[i + window_size]
        smoothed.append(current_sum / window_size)
    return smoothed

def bidirectional_smooth(data: list[float], window_size: int) -> list[float]:
    if len(data) < 3:
        return data.copy()
    pass1 = smooth_signal(data, window_size)
    pass2 = smooth_signal(pass1[::-1], window_size)[::-1]
    return pass2

def get_shot_crop_offsets(video_path: str, width: int, height: int, fps: float, total_frames: int) -> list[int]:
    """
    Divides the video into shots, analyzes each shot to find the speaker's face/motion,
    and returns a list of crop_x offsets for every frame in the video.
    """
    cuts = detect_shot_boundaries(video_path, fps)
    
    # Create shot intervals: [(start, end), ...]
    shots = []
    for i in range(len(cuts)):
        start = cuts[i]
        end = cuts[i+1] if i+1 < len(cuts) else total_frames
        shots.append((start, end))
        
    logger.info(f"Shot-by-shot crop analysis: detected {len(shots)} shots in segment.")
    # Open video
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            logger.error(f"Failed to open video in get_shot_crop_offsets: {video_path}")
            crop_w_base = int(height * 9 / 16)
            crop_w_base = (crop_w_base // 2) * 2
            static_center = max(0, min(width - crop_w_base, (width - crop_w_base) // 2))
            return [static_center] * total_frames

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if actual_w > 0 and actual_h > 0:
            width = actual_w
            height = actual_h

        crop_w_base = int(height * 9 / 16)
        crop_w_base = (crop_w_base // 2) * 2
        
        # Load Haar cascade
        cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            logger.warning("Haar cascade classifier is empty or failed to load. Falling back to motion-only tracking.")
        
        # Downscale factor for performance (we resize frames to process faster)
        scale_factor = 0.25 if width > 960 else 0.5
        inv_scale = 1.0 / scale_factor
        
        # Analysis sampling interval (run face detection on every K-th frame to keep it extremely fast)
        K = 3
        
        crop_x_by_frame = []

        # Track overall face position persistence across frames
        last_seen_face_cx = width / 2.0
        face_lost_counter = 0

        for shot_idx, (start, end) in enumerate(shots):
            shot_len = end - start
            if shot_len <= 0:
                continue
                
            logger.info(f"Analyzing shot {shot_idx+1}/{len(shots)}: frames {start} to {end} (len={shot_len})")
            
            # Frame indices we will analyze in this shot
            analyze_indices = list(range(start, end, K))
            if (end - 1) not in analyze_indices:
                analyze_indices.append(end - 1)
                
            # Store raw target CX coordinates mapped to frame indices
            raw_cx_targets = {}
            
            prev_gray = None
            
            for idx in analyze_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if not ret:
                    raw_cx_targets[idx] = last_seen_face_cx
                    continue
                    
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Try to detect faces
                faces = []
                if not face_cascade.empty():
                    small_gray = cv2.resize(gray, (0, 0), fx=scale_factor, fy=scale_factor)
                    faces = face_cascade.detectMultiScale(
                        small_gray,
                        scaleFactor=1.1,
                        minNeighbors=4,
                        minSize=(15, 15)
                    )
                    
                # Compute motion difference if we have a previous frame
                motion_thresh = None
                if prev_gray is not None:
                    diff = cv2.absdiff(gray, prev_gray)
                    _, motion_thresh = cv2.threshold(diff, 15, 255, cv2.THRESH_BINARY)
                prev_gray = gray
                
                chosen_cx = None
                
                if len(faces) > 0:
                    best_score = -1.0
                    best_face_cx = None
                    
                    for (fx, fy, fw, fh) in faces:
                        orig_x = fx * inv_scale
                        orig_y = fy * inv_scale
                        orig_w = fw * inv_scale
                        orig_h = fh * inv_scale
                        cx = orig_x + orig_w / 2.0
                        area = orig_w * orig_h
                        
                        motion_val = 0.0
                        if motion_thresh is not None:
                            x1, y1 = max(0, int(orig_x)), max(0, int(orig_y))
                            x2, y2 = min(width, int(orig_x + orig_w)), min(height, int(orig_y + orig_h))
                            if (x2 > x1) and (y2 > y1):
                                face_roi = motion_thresh[y1:y2, x1:x2]
                                motion_val = np.mean(face_roi) / 255.0
                        
                        score = area * (1.0 + 2.0 * motion_val)
                        dist = abs(cx - last_seen_face_cx)
                        dist_penalty = math.exp(-dist / (width * 0.25))
                        score *= (0.4 + 0.6 * dist_penalty)
                        
                        if score > best_score:
                            best_score = score
                            best_face_cx = cx
                    
                    if best_face_cx is not None:
                        chosen_cx = best_face_cx
                        last_seen_face_cx = chosen_cx
                        face_lost_counter = 0
                        
                if chosen_cx is None:
                    face_lost_counter += 1
                    if face_lost_counter < int(1.0 * fps / K):
                        chosen_cx = last_seen_face_cx
                    else:
                        motion_cx = None
                        if motion_thresh is not None:
                            moments = cv2.moments(motion_thresh)
                            if moments["m00"] > 5000:
                                motion_cx = moments["m10"] / moments["m00"]
                                
                        if motion_cx is not None:
                            chosen_cx = motion_cx
                        else:
                            chosen_cx = last_seen_face_cx * (1.0 - _FACE_DRIFT_SPEED) + (width / 2.0) * _FACE_DRIFT_SPEED
                            
                raw_cx_targets[idx] = chosen_cx
                last_seen_face_cx = chosen_cx
                
            # Interpolate for all frames in the shot
            shot_cx_targets = []
            for frame_idx in range(start, end):
                if frame_idx in raw_cx_targets:
                    shot_cx_targets.append(raw_cx_targets[frame_idx])
                else:
                    lower_idx = max([k for k in analyze_indices if k < frame_idx], default=analyze_indices[0])
                    upper_idx = min([k for k in analyze_indices if k > frame_idx], default=analyze_indices[-1])
                    
                    if lower_idx == upper_idx:
                        shot_cx_targets.append(raw_cx_targets[lower_idx])
                    else:
                        t_val = (frame_idx - lower_idx) / (upper_idx - lower_idx)
                        val = raw_cx_targets[lower_idx] * (1.0 - t_val) + raw_cx_targets[upper_idx] * t_val
                        shot_cx_targets.append(val)
                        
            # Apply zero phase-lag bidirectional smoothing within the shot boundaries
            smoothing_window = int(1.5 * fps)
            smoothed_cx = bidirectional_smooth(shot_cx_targets, smoothing_window)
            
            # Convert to crop_x offsets (centered on smooth target cx) and clamp
            for cx in smoothed_cx:
                crop_x = int(cx - crop_w_base / 2)
                crop_x = max(0, min(width - crop_w_base, crop_x))
                crop_x_by_frame.append(crop_x)
    finally:
        cap.release()
    
    if len(crop_x_by_frame) < total_frames:
        pad_val = crop_x_by_frame[-1] if crop_x_by_frame else (width - crop_w_base) // 2
        crop_x_by_frame.extend([pad_val] * (total_frames - len(crop_x_by_frame)))
    elif len(crop_x_by_frame) > total_frames:
        crop_x_by_frame = crop_x_by_frame[:total_frames]
        
    return crop_x_by_frame


def extract_clip(input_path: str, start: float, end: float, output_path: str, srt_path: str = None) -> str:
    """Extracts a clip using OpenCV face-tracking to crop to 9:16 portrait ratio, with standard center-crop fallback."""
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg is not installed or not in PATH. Cannot extract video clips.")
    
    duration = end - start
    width, height = get_video_resolution(input_path)
    logger.info(f"Detected video resolution: {width}x{height}")

    # Audio vocal tuning filter (vocal band pass without lookahead delay to keep sync perfect)
    audio_filter = f"highpass=f=100,lowpass=f=8000,afade=t=out:st={duration - 0.5:.2f}:d=0.5"
    
    # If the video is already portrait/square, slice and scale to 1080x1920.
    if width <= height:
        logger.info("Video is already portrait or square. Slicing and scaling to 1080x1920.")
        vf_str = "scale=1080:1920"
        if srt_path:
            srt_filter_path = escape_ffmpeg_path(srt_path)
            vf_str = f"scale=1080:1920,subtitles='{srt_filter_path}'"
        vf_args = ["-vf", vf_str]
        
        has_aud = has_audio(input_path)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", input_path,
            "-t", str(duration),
            "-c:v", "libx264",
        ] + vf_args
        
        if has_aud:
            cmd += [
                "-af", audio_filter,
                "-c:a", "aac",
                "-b:a", "192k",
            ]
        else:
            cmd += ["-an"]
            
        cmd += [
            "-preset", "fast",
            "-crf", "15",
            output_path
        ]
        subprocess.run(cmd, check=True)
        return output_path

    # Generate temporary file paths in the output directory
    output_dir = os.path.dirname(output_path)
    if not output_dir:
        output_dir = "."
    base_name = os.path.basename(output_path)
    base_name_no_ext, _ = os.path.splitext(base_name)
    
    temp_segment = os.path.join(output_dir, f"{base_name_no_ext}_temp_segment.mp4")
    temp_cropped = os.path.join(output_dir, f"{base_name_no_ext}_temp_cropped.avi")
    
    # Parse subtitles for B-roll Slideshow and Popups
    subtitles = parse_ass_subtitles(srt_path)
    slide_events = []
    last_slide_end = -10.0
    for sub in subtitles:
        if sub["emoji"] and sub["start"] >= 2.0 and sub["end"] <= (duration - 2.0):
            if sub["start"] - last_slide_end >= 8.0:
                slide_events.append(sub)
                last_slide_end = sub["end"]
                
    try:
        # Step 1: Extract the segment without cropping first (keeps original audio/video sync)
        has_aud = has_audio(input_path)
        cmd_segment = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", input_path,
            "-t", str(duration),
            "-r", "30",
            "-c:v", "libx264",
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
            
        cmd_segment += [
            "-preset", "ultrafast",
            "-crf", "22",
            temp_segment
        ]
        logger.info(f"Extracting temporary segment: {' '.join(cmd_segment)}")
        res_seg = subprocess.run(cmd_segment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_seg.returncode != 0:
            raise RuntimeError(f"Failed to extract temp segment: {res_seg.stderr}")
        
        # Step 2: Open segment using OpenCV to perform face detection and cropping
        cap = None
        out = None
        try:
            cap = cv2.VideoCapture(temp_segment)
            if not cap.isOpened():
                raise RuntimeError(f"Failed to open temp segment with OpenCV: {temp_segment}")
            
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_w > 0 and actual_h > 0:
                width = actual_w
                height = actual_h

            # Fixed crop output canvas size (9:16 aspect ratio)
            crop_w_base = int(height * 9 / 16)
            crop_w_base = (crop_w_base // 2) * 2
            
            # Force FPS to 30.0 to prevent VFR drift (since we force CFR -r 30 during segment extraction)
            fps = 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                total_frames = int(duration * fps)
                
            # Get shot crop offsets for all frames
            crop_x_by_frame = get_shot_crop_offsets(temp_segment, width, height, fps, total_frames)
            
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            out = cv2.VideoWriter(temp_cropped, fourcc, fps, (1080, 1920))
            
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
                            logger.warning("No frames were read at all from the video stream.")
                            break
                        frame = last_valid_frame
                    else:
                        last_valid_frame = frame
                else:
                    frame = last_valid_frame
                
                t = frame_index / fps
                
                # Get the crop offset for this frame
                crop_x = crop_x_by_frame[min(frame_index, len(crop_x_by_frame) - 1)]
                
                # Crop horizontally (stable, locked to active speaker), full vertical height
                cropped_frame = frame[0:height, crop_x:crop_x + crop_w_base]
                
                # Upscale cropped frame to standard YouTube Shorts full HD resolution (1080x1920)
                cropped_frame = cv2.resize(cropped_frame, (1080, 1920), interpolation=cv2.INTER_CUBIC)
                
                # Check for active full-screen slide event
                active_slide = None
                for slide in slide_events:
                    if slide["start"] <= t <= slide["end"]:
                        active_slide = slide
                        break
                        
                if active_slide:
                    # Render slide frame
                    slide_frame = create_broll_slide(1080, 1920, active_slide["clean_text"], active_slide["emoji"], t)
                    
                    # Whip pan transitions (8 frames)
                    td = 8.0 / fps
                    if t < active_slide["start"] + td:
                        # Transition In
                        progress = (t - active_slide["start"]) / td
                        offset_x = int(progress * 1080)
                        combined_frame = np.zeros_like(cropped_frame)
                        combined_frame[:, 0 : 1080 - offset_x] = cropped_frame[:, offset_x : 1080]
                        combined_frame[:, 1080 - offset_x : 1080] = slide_frame[:, 0 : offset_x]
                    elif t > active_slide["end"] - td:
                        # Transition Out
                        progress = (active_slide["end"] - t) / td
                        offset_x = int(progress * 1080)
                        combined_frame = np.zeros_like(cropped_frame)
                        combined_frame[:, 0 : 1080 - offset_x] = slide_frame[:, offset_x : 1080]
                        combined_frame[:, 1080 - offset_x : 1080] = cropped_frame[:, 0 : offset_x]
                    else:
                        combined_frame = slide_frame
                else:
                    combined_frame = cropped_frame
                    
                    # Check for active keyword popup (not during a full-screen slide)
                    active_popup = None
                    for sub in subtitles:
                        if sub["start"] <= t <= sub["end"] and sub not in slide_events:
                            if sub["highlight"] or sub["emoji"]:
                                active_popup = sub
                                break
                                
                    if active_popup:
                        elapsed = t - active_popup["start"]
                        event_dur = active_popup["end"] - active_popup["start"]
                        if elapsed < 0.2:
                            scale = elapsed / 0.2
                        elif event_dur - elapsed < 0.15:
                            scale = (event_dur - elapsed) / 0.15
                        else:
                            scale = 1.0
                        combined_frame = draw_popup_card(
                            combined_frame, 
                            active_popup["highlight"] or active_popup["clean_text"], 
                            active_popup["emoji"], 
                            scale
                        )
                
                out.write(combined_frame)
                frame_index += 1
        finally:
            if cap is not None:
                cap.release()
            if out is not None:
                out.release()
        
        # Step 3: Merge original audio from temp_segment with cropped video temp_cropped and burn subtitles
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
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-preset", "fast",
                    "-crf", "15",
                    "-shortest",
                    output_path
                ]
            else:
                cmd_merge = [
                    "ffmpeg", "-y",
                    "-i", temp_cropped,
                    "-vf", sub_filter,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "15",
                    output_path
                ]
        else:
            if has_audio(temp_segment):
                cmd_merge = [
                    "ffmpeg", "-y",
                    "-i", temp_cropped,
                    "-i", temp_segment,
                    "-filter_complex", f"[1:a]{audio_filter}[a]",
                    "-map", "0:v",
                    "-map", "[a]",
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-preset", "fast",
                    "-crf", "15",
                    "-shortest",
                    output_path
                ]
            else:
                cmd_merge = [
                    "ffmpeg", "-y",
                    "-i", temp_cropped,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "15",
                    output_path
                ]
            
        logger.info(f"Merging audio and video: {' '.join(cmd_merge)}")
        res_merge = subprocess.run(cmd_merge, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_merge.returncode != 0:
            raise RuntimeError(f"Failed to merge audio and video: {res_merge.stderr}")
            
    except Exception as e:
        logger.error(f"OpenCV face tracking crop failed: {e}. Falling back to static center crop.")
        # FALLBACK: standard static center crop with subtitles upscaled to 1080x1920
        crop_filter = "crop=trunc(ih*9/16/2)*2:ih,scale=1080:1920"
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
            "-c:v", "libx264",
            "-vf", vf_str,
        ]
        if has_aud:
            cmd_fallback += [
                "-af", audio_filter,
                "-c:a", "aac",
                "-b:a", "192k",
            ]
        else:
            cmd_fallback += ["-an"]
            
        cmd_fallback += [
            "-preset", "fast",
            "-crf", "15",
            output_path
        ]
        subprocess.run(cmd_fallback, check=True)
            
    finally:
        # Clean up temporary files
        for f in [temp_segment, temp_cropped]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    logger.warning(f"Could not delete temp file {f}: {e}")
                    
    logger.info(f"Successfully extracted clip with dynamic face tracking to: {output_path}")
    return output_path
