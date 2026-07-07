import os
import subprocess
import shutil

categories = ["uplifting", "inspirational", "calm", "dramatic", "emotional", "corporate"]
base_dir = "backend/assets/music"

def make_sine_audio(output_path, freq):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=44100",
        "-c:a", "libmp3lame", "-t", "10",
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Created dummy audio: {output_path} ({os.path.getsize(output_path)} bytes)")

def main():
    os.makedirs(base_dir, exist_ok=True)
    frequencies = {
        "uplifting": 330,
        "inspirational": 440,
        "calm": 220,
        "dramatic": 554,
        "emotional": 293,
        "corporate": 392
    }
    for cat in categories:
        cat_dir = os.path.join(base_dir, cat)
        os.makedirs(cat_dir, exist_ok=True)
        # Create track_1 and track_2 for each category
        make_sine_audio(os.path.join(cat_dir, "track_1.mp3"), frequencies[cat])
        make_sine_audio(os.path.join(cat_dir, "track_2.mp3"), frequencies[cat] * 1.5)

if __name__ == "__main__":
    main()
