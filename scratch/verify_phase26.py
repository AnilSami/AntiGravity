import os
import sys
import subprocess

# Ensure we can import from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from music_selector import mix_music_into_clip
from overlays import add_like_overlay

def run_verification():
    print("=== Phase 26 Verification Pipeline ===")
    
    # 1. Slice 15 seconds of the source video
    source_video = os.path.abspath("../backend/output/cache/Gb6RK32q4Qg.mp4")
    clean_clip = os.path.abspath("clean_clip.mp4")
    
    if not os.path.exists(source_video):
        print(f"Error: Source video not found at {source_video}")
        return
        
    print(f"Slicing 15s from {source_video}...")
    slice_cmd = [
        "ffmpeg", "-y",
        "-ss", "785.36",
        "-i", source_video,
        "-t", "15.0",
        "-c:v", "copy",
        "-c:a", "copy",
        clean_clip
    ]
    subprocess.run(slice_cmd, check=True)
    print(f"Clean clip sliced to: {clean_clip}")
    
    # 2. Select music file
    cache_dir = "../backend/output/cache"
    candidates = [
        os.path.join(cache_dir, f) for f in os.listdir(cache_dir)
        if f.startswith("music_") and f.endswith(".mp3") and not f.endswith("dummy.mp3") and os.path.getsize(os.path.join(cache_dir, f)) > 100 * 1024
    ]
    if candidates:
        music_file = os.path.abspath(candidates[0])
        print(f"Using valid cached music file: {music_file}")
    else:
        # Fallback to dummy if nothing else exists
        music_file = os.path.abspath("../backend/output/cache/music_dummy.mp3")
        print(f"Fallback to music file: {music_file}")

    # 3. Mix music into clean clip
    print("Mixing music into clean clip...")
    # Using volume_pct=8 as requested for default Phase 26 volume
    mixed_clip = mix_music_into_clip(
        clip_path=clean_clip,
        music_path=music_file,
        volume_pct=8,
        fade_in_secs=1.0,
        fade_out_secs=2.0,
        duration=15.0,
        clip_id="verify_p26"
    )
    print(f"Mixed clip path returned: {mixed_clip}")
    
    # 4. Apply Like Prompt Overlay (T1~1.8s, T2~7.5s, T3~13.0s)
    print("Applying Like animation overlay...")
    final_clip = add_like_overlay(
        clip_path=mixed_clip,
        clip_id="verify_p26",
        duration=15.0
    )
    print(f"Final clip path: {final_clip}")
    
    # 5. Extract screenshots to verify visual overlay
    print("Extracting verification screenshots at T1, T2, T3...")
    os.makedirs("screenshots", exist_ok=True)
    
    # T1 = 15 * 0.12 = 1.8s (let's screenshot at 1.9s)
    # T2 = 15 * 0.50 = 7.5s (let's screenshot at 7.6s)
    # T3 = 15 * 0.87 = 13.05s (let's screenshot at 13.1s)
    
    for t_val, label in [(1.9, "T1_start"), (7.6, "T2_middle"), (13.1, "T3_end")]:
        output_img = os.path.abspath(f"screenshots/screenshot_{label}.png")
        screenshot_cmd = [
            "ffmpeg", "-y",
            "-ss", str(t_val),
            "-i", final_clip,
            "-vframes", "1",
            "-q:v", "2",
            output_img
        ]
        subprocess.run(screenshot_cmd, capture_output=True)
        if os.path.exists(output_img):
            print(f"Saved screenshot for {label} to {output_img}")
        else:
            print(f"Failed to capture screenshot for {label}")

    print("Verification execution complete.")

if __name__ == "__main__":
    run_verification()
