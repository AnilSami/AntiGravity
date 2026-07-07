import os
import sys
from unittest.mock import patch
import logging

# Set up logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Change directory to backend to ensure paths resolve correctly
os.chdir("backend")

# Add backend folder to python path
sys.path.append(os.getcwd())

from music_selector import mix_music_into_clip, add_impact_sounds

def clean_cache(clip_id):
    cache_meta = f"output/cache/sfx_{clip_id}_meta.json"
    mixed_clip = f"output/clips/{clip_id}_with_music.mp4"
    
    if os.path.exists(cache_meta):
        os.remove(cache_meta)
        print(f"Cleaned cache file: {cache_meta}")
    if os.path.exists(mixed_clip):
        os.remove(mixed_clip)
        print(f"Cleaned mixed clip file: {mixed_clip}")

def main():
    clip_id = "real_test_clip"
    clean_cache(clip_id)
    
    clip_path = "output/cache/5r6L9rD-Euw.mp4"
    if not os.path.exists(clip_path):
        print(f"[ERROR] Source video file not found at {clip_path}")
        return
        
    music_cache_dir = "output/cache"
    music_files = [f for f in os.listdir(music_cache_dir) if f.startswith("music_") and f.endswith(".mp3")]
    if not music_files:
        print("[ERROR] No cached music files found to use in test.")
        return
    music_path = os.path.join(music_cache_dir, music_files[0])
    print(f"Using video: {clip_path}")
    print(f"Using music: {music_path}")
    
    # 1. Test mix_music_into_clip
    print("\n--- TEST: MUSIC MIXING ---")
    mixed_path = mix_music_into_clip(
        clip_path=clip_path,
        music_path=music_path,
        volume_pct=20,
        fade_in_secs=1.0,
        fade_out_secs=2.0,
        duration=15.0,
        clip_id=clip_id
    )
    print(f"Mixed Clip Output Path: {mixed_path}")

    # 2. Test add_impact_sounds
    print("\n--- TEST: IMPACT SFX OVERLAY ---")
    mock_moments = [
        {"timestamp_hint": "middle", "word": "panic", "effect_type": "ding"},
        {"timestamp_hint": "late", "word": "blackmail", "effect_type": "impact"}
    ]
    
    # Temporarily set ELEVENLABS_API_KEY to a mock key if it is empty so it triggers download mock
    old_elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
    os.environ["ELEVENLABS_API_KEY"] = "mock"
    
    with patch("music_selector._identify_impact_moments", return_value=mock_moments):
        result = add_impact_sounds(
            clip_path=mixed_path,
            clip_text="patterns of activity they identified as panic and blackmail",
            hook_line="They are starting to get some clues.",
            clip_id=clip_id,
            api_key="real-key",
            duration=15.0
        )
        
    if old_elevenlabs_key is not None:
        os.environ["ELEVENLABS_API_KEY"] = old_elevenlabs_key
        
    print("\n--- FINAL RESULT ---")
    import json
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
