import os
import sys
import re
import subprocess

# Ensure we can import from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from music_selector import mix_music_into_clip, _detect_audio_loudness
from overlays import add_like_overlay

def measure_loudness(file_path):
    cmd = [
        "ffmpeg", "-i", file_path,
        "-af", "volumedetect",
        "-f", "null", "-"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        mean_match = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", res.stderr)
        max_match = re.search(r"max_volume:\s*(-?\d+\.?\d*)\s*dB", res.stderr)
        
        mean_vol = float(mean_match.group(1)) if mean_match else -99.9
        max_vol = float(max_match.group(1)) if max_match else -99.9
        return mean_vol, max_vol
    except Exception as e:
        print(f"Error measuring loudness for {file_path}: {e}")
        return -99.9, -99.9

def generate_comparisons():
    print("=== Generating Comparison Clips (6%, 8%, 10%) ===")
    
    clean_clip = os.path.abspath("clean_clip.mp4")
    if not os.path.exists(clean_clip):
        print(f"Error: clean_clip.mp4 not found at {clean_clip}")
        return
        
    cache_dir = "../backend/output/cache"
    candidates = [
        os.path.join(cache_dir, f) for f in os.listdir(cache_dir)
        if f.startswith("music_") and f.endswith(".mp3") and not f.endswith("dummy.mp3") and os.path.getsize(os.path.join(cache_dir, f)) > 100 * 1024
    ]
    if not candidates:
        print("Error: No valid music file found in cache.")
        return
        
    music_file = os.path.abspath(candidates[0])
    print(f"Using music track: {music_file}")
    
    results = {}
    
    for vol in [6, 8, 10]:
        print(f"\nProcessing version with music volume = {vol}%...")
        
        # Mix music with specific volume percentage (bypass cache using custom clip_id prefix)
        clip_id = f"compare_vol_{vol}"
        mixed_file = mix_music_into_clip(
            clip_path=clean_clip,
            music_path=music_file,
            volume_pct=vol,
            fade_in_secs=1.0,
            fade_out_secs=2.0,
            duration=15.0,
            clip_id=clip_id
        )
        
        # Burn like overlay
        final_file = add_like_overlay(
            clip_path=mixed_file,
            clip_id=clip_id,
            duration=15.0
        )
        
        print(f"Generated final comparison file: {final_file}")
        
        # Measure final mixed file loudness & peak
        mean_l, max_l = measure_loudness(final_file)
        results[vol] = {
            "path": final_file,
            "mean_volume": mean_l,
            "max_volume": max_l
        }
        print(f"Result for {vol}%: mean_volume={mean_l} dB, max_volume={max_l} dB")
        
    print("\n=== COMPARISON SUMMARY ===")
    for vol, data in results.items():
        print(f"Music Volume: {vol:2d}% | Mean Loudness: {data['mean_volume']:6.1f} dB | Peak Level: {data['max_volume']:5.1f} dB | File: {os.path.basename(data['path'])}")

if __name__ == "__main__":
    generate_comparisons()
