import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

# Ensure Windows terminal outputs UTF-8 characters cleanly without charmap crashes
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add backend folder to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from analyzer import get_video_id, fetch_transcript_list, analyze_with_gemini

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("demo_runner")

async def main():
    load_dotenv(dotenv_path="backend/.env")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    # Check command-line arguments to override API Key with mock
    force_mock = False
    for arg in sys.argv:
        if arg.lower() in ["mock", "--mock"]:
            force_mock = True
            break
            
    if force_mock:
        print("[INFO] Forcing Mock Mode via command-line argument.")
        api_key = "mock"
    elif not api_key:
        print("[INFO] API Key not found in .env, running in Mock Mode.")
        api_key = "mock"
    else:
        # Mask key for printing
        masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else api_key
        print(f"[INFO] Using configured API Key: {masked_key}")

    # Use a default engaging video (Steve Jobs Commencement Speech) or allow passing one via command-line
    url = "https://www.youtube.com/watch?v=UF8uR6Z6KLc"
    for arg in sys.argv[1:]:
        if arg.lower() not in ["mock", "--mock"]:
            url = arg
            break
    num_clips = 3
    
    print(f"\n[LAUNCH] Launching Multi-Agent Pipeline for URL: {url}")
    print("=" * 80)
    
    try:
        # Step 1: Fetch Transcript
        print("\n[FETCH] Step 1: Fetching transcript from YouTube...")
        video_id = get_video_id(url)
        raw_transcript = fetch_transcript_list(video_id)
        print(f"[SUCCESS] Transcript fetched successfully! Got {len(raw_transcript)} lines.")
        
        # Format transcript lines
        formatted_lines = []
        for idx, entry in enumerate(raw_transcript):
            start = entry.start
            end = entry.start + entry.duration
            timestamp = f"[{start:.2f} - {end:.2f}]"
            text = entry.text.replace('\n', ' ')
            formatted_lines.append(f"[{idx}] {timestamp} {text}")
        transcript_text = "\n".join(formatted_lines)
        
        # Step 2: Run Multi-Agent Analysis
        print("\n[LLM] Step 2: Running Multi-Agent LLM Analysis (Scout -> Curator -> Editor -> Publisher)...")
        print("-" * 80)
        
        clips_data = analyze_with_gemini(
            transcript=transcript_text,
            raw_transcript=raw_transcript,
            api_key=api_key,
            num_clips=num_clips
        )
        
        print("-" * 80)
        print(f"[SUCCESS] Multi-Agent Extraction Complete! Identified {len(clips_data)} high-virality clips.")
        
        # Step 3: Print detailed agent outputs
        print("\n[RESULTS] Final Clip Extraction Results:")
        print("=" * 80)
        for idx, clip in enumerate(clips_data):
            print(f"\n[CLIP] Clip #{idx+1}: {clip['title']}")
            print(f"  - Timeline: {clip['start_time']}s - {clip['end_time']}s (Duration: {round(clip['end_time'] - clip['start_time'], 2)}s)")
            print(f"  - Global Indices: [{clip['start_index']} - {clip['end_index']}]")
            print(f"  - Virality Reason: {clip['reason']}")
            print(f"  - YouTube Shorts Title: {clip['shorts_title']}")
            print(f"  - Shorts Description: {clip['shorts_description']}")
            print(f"  - Search Tags: {', '.join(clip['shorts_tags'])}")
            print("-" * 80)
            
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
