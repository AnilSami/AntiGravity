import os
import sys
import subprocess

# Add backend folder to python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend"))

from overlays import add_like_overlay

def create_synthetic_clip():
    os.makedirs("scratch", exist_ok=True)
    clip_path = "scratch/test_overlay_input.mp4"
    
    # Create a 5-second video clip with a 440Hz audio tone
    print("Generating synthetic video clip...")
    cmd_clip = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-t", "5",
        clip_path
    ]
    subprocess.run(cmd_clip, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return clip_path

def probe_output(file_path):
    print(f"\nProbing output file: {file_path}")
    cmd = ["ffprobe", "-show_streams", "-show_format", "-print_format", "json", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)

if __name__ == "__main__":
    clip = os.path.abspath(create_synthetic_clip())
    
    # Run add_like_overlay
    print("\nApplying like prompt overlay...")
    os.chdir("backend")
    os.environ["ELEVENLABS_API_KEY"] = "mock"
    # Ensure there is a cached mp3 so ElevenLabs mock copies it
    os.makedirs("output/cache", exist_ok=True)
    with open("output/cache/music_dummy.mp3", "wb") as f:
        f.write(b"X" * 2048)
        
    out_path = add_like_overlay(
        clip_path=clip,
        clip_id="test_overlay_id",
        duration=5.0
    )
    
    print(f"Output path returned: {out_path}")
    if os.path.exists(out_path):
        probe_output(out_path)
    else:
        print("Error: Output file not created!")
