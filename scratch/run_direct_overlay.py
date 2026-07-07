import os
import sys
import logging

# Ensure we can import from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

# Configure logging to print to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)

from overlays import add_like_overlay

def test_direct():
    clean_clip = os.path.abspath("clean_clip.mp4")
    print(f"Input clip: {clean_clip} (exists: {os.path.exists(clean_clip)})")
    
    final_clip = add_like_overlay(
        clip_path=clean_clip,
        clip_id="verify_p26_direct",
        duration=15.0
    )
    print("Returned final clip path:", final_clip)

if __name__ == "__main__":
    test_direct()
