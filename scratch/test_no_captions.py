import sys
import os
sys.path.append("d:/Desktop/LLM/backend")
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

test_ids = [
    "tNkZs56ZoDM", # Home - Resonance
    "3S9v_1xH1e4", # Chopin
    "W3q8Od5qJio", # Ambient / Lofi
    "V1Pl8CzNzCw", # Instrumental music
    "u7nS_7d_iQA", # Rain sound
    "9E6b3swg090", 
    "kJQP7kiw5Fk"
]

for vid in test_ids:
    print(f"\nChecking Video ID: {vid}")
    
    # 1. Check youtube-transcript-api
    try:
        YouTubeTranscriptApi.list(vid)
        print("  youtube-transcript-api: HAS CAPTIONS")
    except Exception as e:
        print(f"  youtube-transcript-api: NO ({type(e).__name__})")
        
    # 2. Check yt-dlp subtitles
    url = f"https://www.youtube.com/watch?v={vid}"
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'source_address': '0.0.0.0'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subtitles = info.get("subtitles")
            automatic_captions = info.get("automatic_captions")
            print(f"  yt-dlp manual subtitles: {list(subtitles.keys()) if subtitles else 'None'}")
            print(f"  yt-dlp auto captions: {list(automatic_captions.keys()) if automatic_captions else 'None'}")
    except Exception as e:
        print(f"  yt-dlp error: {e}")
