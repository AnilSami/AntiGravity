import os
import sys
import re
import subprocess

# Ensure we can import from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from music_selector import _detect_audio_loudness

def measure_speech_alone():
    print("=== Measuring Speech Track (Voice Only) Post-Adaptive Normalization ===")
    
    clean_clip = os.path.abspath("clean_clip.mp4")
    if not os.path.exists(clean_clip):
        print(f"Error: clean_clip.mp4 not found.")
        return
        
    # 1. Detect clean speech loudness
    mean_vol, max_vol = _detect_audio_loudness(clean_clip, "verify_speech_clean")
    print(f"Original clean speech: mean={mean_vol} dB, max={max_vol} dB")
    
    # 2. Calculate gain
    target_mean = -14.0
    gain_db = target_mean - mean_vol
    gain_db = max(0.0, min(12.0, gain_db))
    print(f"Adaptive gain to apply: +{gain_db:.2f} dB")
    
    # 3. Render a temporary voice-only file with the gain and limiter applied
    voice_only_output = os.path.abspath("voice_only_normalized.wav")
    
    filter_graph = (
        f"aformat=sample_rates=44100:channel_layouts=stereo,"
        f"volume={gain_db:.2f}dB,"
        f"alimiter=level_in=1.0:level_out=1.0:limit=0.95:attack=5:release=80"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", clean_clip,
        "-af", filter_graph,
        voice_only_output
    ]
    
    subprocess.run(cmd, capture_output=True)
    
    # 4. Measure the loudness of the resulting voice-only track
    cmd_measure = [
        "ffmpeg", "-i", voice_only_output,
        "-af", "volumedetect",
        "-f", "null", "-"
    ]
    res = subprocess.run(cmd_measure, capture_output=True, text=True)
    
    mean_match = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", res.stderr)
    max_match = re.search(r"max_volume:\s*(-?\d+\.?\d*)\s*dB", res.stderr)
    
    norm_mean = float(mean_match.group(1)) if mean_match else -99.9
    norm_max = float(max_match.group(1)) if max_match else -99.9
    
    print("\n=== NORMALIZED SPEECH RESULTS ===")
    print(f"Normalized Speech Mean Loudness: {norm_mean} dB")
    print(f"Normalized Speech Peak Level:    {norm_max} dB")
    
    # Cleanup
    if os.path.exists(voice_only_output):
        os.remove(voice_only_output)

if __name__ == "__main__":
    measure_speech_alone()
