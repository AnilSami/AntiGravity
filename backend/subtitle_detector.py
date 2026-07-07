import cv2
import numpy as np
import logging
import os

logger = logging.getLogger("subtitle_detector")

def detect_subtitle_zone(video_path: str) -> int:
    """
    Detects the vertical subtitle zone in a video.
    Returns the height of the subtitle zone in pixels, measured from the bottom of the frame,
    or 0 if no subtitle zone is detected.
    
    Uses a dual-signal approach calibrated against production TrueType-rendered subtitles:
      1. Canny edge density > 3% (anti-aliased text produces ~5-10% density, not 15%)
      2. Local variance > 1000 (text regions have high per-row variance from letter shapes)
    Both signals must agree for a band to count as a subtitle candidate.
    """
    if not os.path.exists(video_path):
        logger.warning(f"Video file does not exist: {video_path}")
        return 0

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning(f"Cannot open video file: {video_path}")
        return 0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        return 0

    # 1. Sample 20 evenly spaced frames
    num_samples = 20
    if total_frames > num_samples:
        frame_indices = [int(i * (total_frames - 1) / (num_samples - 1)) for i in range(num_samples)]
    else:
        frame_indices = list(range(total_frames))

    band_h = 40
    detected_positions = []
    detected_brightness = []

    # Thresholds calibrated from production TrueType font tests:
    # - Anti-aliased text at 32px font on 1280x720 produces 5-10% Canny(50,150) edge density
    # - The same text produces per-row variance of 1900-4300
    # - Plain video backgrounds without text: 0-2.5% edge density, variance < 500
    EDGE_DENSITY_THRESHOLD = 0.03      # 3% (was 15% - too high for anti-aliased text)
    VARIANCE_THRESHOLD = 1000          # Per-row variance (text vs background discriminator)
    CONTRAST_THRESHOLD = 30.0          # Minimum std dev of band brightness

    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue

        height, width = frame.shape[:2]
        bottom_20_start = int(height * 0.8)
        bottom_zone = frame[bottom_20_start:height, :]
        
        # 2. Convert bottom zone to grayscale and detect edges
        gray_zone = cv2.cvtColor(bottom_zone, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray_zone, 50, 150)

        # 3. Scan bottom 20% in overlapping bands of height 40px
        bottom_h = height - bottom_20_start
        best_y = -1
        best_score = 0.0
        best_brightness = 0.0

        for y in range(0, bottom_h - band_h + 1, 5):
            band_edges = edges[y : y + band_h, :]
            band_gray = gray_zone[y : y + band_h, :]
            
            # Signal 1: Canny edge density
            density = np.mean(band_edges > 0)
            
            # Signal 2: Per-row variance (high for text, low for uniform areas)
            variance = np.mean(np.var(band_gray.astype(np.float32), axis=1))
            
            # Signal 3: Overall contrast (std dev of brightness)
            contrast = np.std(band_gray.astype(np.float32))
            
            # Dual-signal requirement: both edge density AND variance must pass
            # This prevents false positives from noisy backgrounds (high edges but low variance)
            # and from gradient backgrounds (high variance but low edges)
            if density > EDGE_DENSITY_THRESHOLD and variance > VARIANCE_THRESHOLD and contrast > CONTRAST_THRESHOLD:
                # Score combines both signals for ranking
                score = density * 0.5 + (variance / 10000.0) * 0.3 + (contrast / 100.0) * 0.2
                if score > best_score:
                    best_score = score
                    best_y = y
                    best_brightness = float(np.mean(band_gray))

        if best_y != -1:
            detected_positions.append(best_y)
            detected_brightness.append(best_brightness)

    cap.release()

    # 4. If 50% or more of sampled frames show a subtitle band at the same vertical position
    # (Lowered from 60% because subtitles have gaps between sentences)
    min_detections = max(int(0.50 * len(frame_indices)), 1) if frame_indices else 10
    if len(detected_positions) >= min_detections:
        # Find consistent positions (within ±15 pixels — slightly wider for subtitle position variation)
        consistent_y = None
        max_consistent_count = 0
        consistent_brightness_list = []

        for pos in set(detected_positions):
            # Find all detections within 15 pixels of this position
            indices = [i for i, p in enumerate(detected_positions) if abs(p - pos) <= 15]
            count = len(indices)
            if count >= min_detections and count > max_consistent_count:
                # Also check consistent brightness pattern (subtitle background box or stable brightness)
                brightness_vals = [detected_brightness[i] for i in indices]
                brightness_std = np.std(brightness_vals) if len(brightness_vals) > 1 else 0.0
                
                # A consistent background or text pattern typically has stable average brightness (std < 30.0)
                if brightness_std < 30.0:
                    max_consistent_count = count
                    consistent_y = pos
                    consistent_brightness_list = brightness_vals

        if consistent_y is not None:
            # Subtitle zone starts at bottom_20_start + consistent_y.
            # Height measured from bottom of the frame is height - (bottom_20_start + consistent_y)
            subtitle_zone_height = height - (bottom_20_start + consistent_y)
            logger.info(f"Subtitle zone detected at y-offset {consistent_y} (height: {subtitle_zone_height}px from bottom, std_brightness: {np.std(consistent_brightness_list):.2f})")
            return subtitle_zone_height

    logger.info("No consistent subtitle zone detected")
    return 0

def has_subtitles(video_path: str) -> bool:
    """
    Returns True if a subtitle zone is detected, logging the result.
    """
    height = detect_subtitle_zone(video_path)
    if height > 0:
        logger.info(f"Subtitle zone detected: {height}px from bottom")
        return True
    logger.info("No subtitle zone detected")
    return False
