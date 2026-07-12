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
    
    Supports:
      - Bottom subtitles (returns height > 0 to trigger cropping/exclusion)
      - Middle subtitles (returns 2 to indicate detection without triggering excessive crop)
      - Static graphic filtering (filters out logos, scoreboards, and watermarks using always-on masked edge analysis)
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

    # Sample 25 evenly spaced frames
    num_samples = 25
    if total_frames > num_samples:
        frame_indices = [int(i * (total_frames - 1) / (num_samples - 1)) for i in range(num_samples)]
    else:
        frame_indices = list(range(total_frames))

    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    # Scale-invariant band parameters
    band_h = int(height * 0.05)
    step_y = int(band_h * 0.25)
    if band_h < 15:
        band_h = 15
    if step_y < 4:
        step_y = 4

    # Calibrated thresholds:
    EDGE_DENSITY_THRESHOLD = 0.025      # 2.5% edge density
    VARIANCE_THRESHOLD = 900           # Per-row letter shape variance
    CONTRAST_THRESHOLD = 25.0          # Minimum standard deviation contrast
    MAX_ALWAYS_ON_MASKED = 250         # Max always-on masked edges to reject static logos/watermarks

    # Store detected slices: y_offset -> list of (band_gray, band_edges, mask)
    detected_slices = {}
    detected_scores = {}

    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        # Scan from 25% to 95% height of the frame
        start_y = int(height * 0.25)
        end_y = int(height * 0.95)

        for y in range(start_y, end_y - band_h + 1, step_y):
            band_gray = gray[y : y + band_h, :]
            band_edges = edges[y : y + band_h, :]

            density = np.mean(band_edges > 0)
            variance = np.mean(np.var(band_gray.astype(np.float32), axis=1))
            contrast = np.std(band_gray.astype(np.float32))

            # Count letter blobs and horizontal/vertical features
            contours, _ = cv2.findContours(band_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # First pass: collect contours and their baselines
            valid_contours = []
            baselines = []
            for c in contours:
                x_c, y_c, w_c, h_c = cv2.boundingRect(c)
                if (0.15 * band_h <= h_c <= 0.85 * band_h) and (0.05 * band_h <= w_c <= 1.0 * band_h):
                    if 0.15 <= w_c / h_c <= 2.5:
                        valid_contours.append((c, x_c, y_c, w_c, h_c))
                        baselines.append(y_c + h_c)
            
            letter_count = len(valid_contours)
            x_coords = []
            mask = np.zeros(band_edges.shape, dtype=np.uint8)
            
            # Second pass: only keep contours aligned with the median baseline (to ignore background details)
            if valid_contours:
                median_base = np.median(baselines)
                for c, x_c, y_c, w_c, h_c in valid_contours:
                    y_base = y_c + h_c
                    tolerance = max(int(band_h * 0.12), 3)
                    if abs(y_base - median_base) <= tolerance:
                        x_coords.append((x_c, x_c + w_c))
                        cv2.drawContours(mask, [c], -1, 255, -1)

            # Check horizontal centering, span, and vertical baseline alignment
            span_ok = False
            center_ok = False
            baseline_ok = False

            if x_coords:
                min_x = min(item[0] for item in x_coords)
                max_x = max(item[1] for item in x_coords)
                span = max_x - min_x
                center = (min_x + max_x) / 2
                span_pct = span / width
                center_pct = center / width
                
                # Subtitles span at least 22% of width and are centered
                span_ok = (span_pct >= 0.22)
                center_ok = (0.35 <= center_pct <= 0.65)
                
                # Baseline vertical alignment (std dev of bottom y-coordinates of contours)
                if len(baselines) >= 5:
                    baseline_std = np.std(baselines)
                    baseline_ok = (baseline_std <= 9.5)

            if letter_count >= 5 and span_ok and center_ok and baseline_ok and density > EDGE_DENSITY_THRESHOLD and variance > VARIANCE_THRESHOLD and contrast > CONTRAST_THRESHOLD:
                if y not in detected_slices:
                    detected_slices[y] = []
                    detected_scores[y] = []
                
                # Mask the dilated edges with the contour mask
                dilated_edges = cv2.dilate(band_edges, np.ones((3, 3), np.uint8))
                masked_edges = cv2.bitwise_and(dilated_edges, dilated_edges, mask=mask)
                
                detected_slices[y].append(masked_edges)
                score = density * 0.5 + (variance / 10000.0) * 0.3 + (contrast / 100.0) * 0.2
                detected_scores[y].append(score)

    cap.release()

    # Require detections in at least 30% of sampled frames
    min_detections = max(int(0.30 * len(frame_indices)), 2) if frame_indices else 5
    
    valid_zones = []

    for y, slices in detected_slices.items():
        if len(slices) >= min_detections:
            # Calculate always-on masked edges to identify static logos/watermarks
            mean_edges = np.mean(np.array(slices) > 0, axis=0)
            always_on_count = np.sum(mean_edges > 0.70)

            if always_on_count > MAX_ALWAYS_ON_MASKED:
                logger.info(f"Discarded static graphic at Y={y} (always-on masked edges: {always_on_count})")
                continue

            avg_score = np.mean(detected_scores[y])
            valid_zones.append((y, avg_score))

    if not valid_zones:
        logger.info("No consistent subtitle zone detected")
        return 0

    # Choose the zone with the highest score
    best_y, best_score = max(valid_zones, key=lambda x: x[1])

    # Find the top-most Y position among all bands scoring within 85% of the best score
    # to ensure we capture the full vertical height of the subtitle block.
    high_scoring_y = [y for y, score in valid_zones if score >= 0.85 * best_score]
    top_y = min(high_scoring_y) if high_scoring_y else best_y

    subtitle_zone_height = height - top_y
    if top_y > int(height * 0.65):
        logger.info(f"Bottom subtitle zone detected at Y={top_y} (height: {subtitle_zone_height}px from bottom, score: {best_score:.4f})")
    else:
        logger.info(f"Middle subtitle zone detected at Y={top_y} (height: {subtitle_zone_height}px from bottom, score: {best_score:.4f})")
    return subtitle_zone_height

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
