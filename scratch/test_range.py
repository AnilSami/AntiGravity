import yt_dlp
import os

url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
outtmpl = "scratch/test_range.%(ext)s"

ydl_opts = {
    'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
    'merge_output_format': 'mp4',
    'outtmpl': outtmpl,
    'quiet': False,
    'download_ranges': lambda info_dict, ydl: [{'start_time': 0, 'end_time': 5}],
    'force_keyframes_at_cuts': True,
    'source_address': '0.0.0.0', # Force IPv4
}

try:
    if os.path.exists("scratch/test_range.mp4"):
        os.remove("scratch/test_range.mp4")
except Exception:
    pass

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])

print("Downloaded file size:", os.path.getsize("scratch/test_range.mp4") if os.path.exists("scratch/test_range.mp4") else "None")
