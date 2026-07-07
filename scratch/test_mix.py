import os
import sys
import subprocess

# Add backend folder to python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend"))

from music_selector import mix_music_into_clip

def create_synthetic_files():
    os.makedirs("scratch", exist_ok=True)
    clip_path = "scratch/test_clip.mp4"
    music_path = "scratch/test_music.mp3"
    
    # 1. Create a 5-second video clip with a 440Hz audio tone (simulating voice)
    # Using libx264 for video and aac for audio
    print("Generating synthetic video clip with 440Hz tone...")
    cmd_clip = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-t", "5",
        clip_path
    ]
    subprocess.run(cmd_clip, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 2. Create a 5-second music mp3 with an 880Hz audio tone (simulating music)
    print("Generating synthetic music MP3 with 880Hz tone...")
    cmd_music = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100",
        "-c:a", "libmp3lame", "-t", "5",
        music_path
    ]
    subprocess.run(cmd_music, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    return clip_path, music_path

def probe_output(file_path):
    print(f"\nProbing output file: {file_path}")
    cmd = ["ffprobe", "-show_streams", "-show_format", "-print_format", "json", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)

if __name__ == "__main__":
    clip, music = create_synthetic_files()
    
    # Run mix_music_into_clip
    print("\nMixing music into clip...")
    out_path = mix_music_into_clip(
        clip_path=clip,
        music_path=music,
        volume_pct=20,
        fade_in_secs=0.5,
        fade_out_secs=0.5,
        duration=5.0,
        clip_id="test_mix_id"
    )
    
    print(f"Output path returned: {out_path}")
    if os.path.exists(out_path):
        probe_output(out_path)
    else:
        print("Error: Output file not created!")
