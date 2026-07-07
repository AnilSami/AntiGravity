import os
import subprocess

clip_path = r"D:\Desktop\LLM\scratch\clean_clip.mp4"
custom_asset = r"D:\Desktop\LLM\assets\animations\like_button.webm"
output_path = r"D:\Desktop\LLM\scratch\test_overlay_run.mp4"

# Let's run a test FFmpeg overlay command directly and look at the stderr!
# x = w*0.06, y = H*0.28
# Scale = 180x180
# Enable = between(t, 1.8, 3.3)
filter_complex = (
    "[1:v]scale=180:180:force_original_aspect_ratio=decrease[asset_scaled];"
    "[0:v][asset_scaled]overlay=x=W*0.06:y=H*0.28:enable='between(t,1.8,3.3)'[vout]"
)

cmd = [
    "ffmpeg", "-y",
    "-i", clip_path,
    "-stream_loop", "-1", "-i", custom_asset,
    "-filter_complex", filter_complex,
    "-map", "[vout]",
    "-map", "0:a",
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-t", "15.0",
    output_path
]

print("Running command:", " ".join(cmd))
res = subprocess.run(cmd, capture_output=True, text=True)
print("\n=== FFmpeg Return Code:", res.returncode)
print("\n=== FFmpeg Stderr (last 1000 chars): ===")
print(res.stderr[-1500:])
