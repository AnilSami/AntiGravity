import requests
import json
import time
import os
import sys

BASE_URL = "http://127.0.0.1:8000"

# Choose 6 videos: 5 cached, 1 new to download
videos_to_test = [
    {"url": "https://www.youtube.com/watch?v=iG9CE55wbtY", "name": "Video 1 (Manual Captions - Cached)"},
    {"url": "https://www.youtube.com/watch?v=qp0HIF3SfI4", "name": "Video 2 (Manual Captions - Cached)"},
    {"url": "https://www.youtube.com/watch?v=UF8uR6Z6KLc", "name": "Video 3 (Manual Captions - Cached)"},
    {"url": "https://www.youtube.com/watch?v=aAPpQC-3EyE", "name": "Video 4 (Auto Captions - Cached)"},
    {"url": "https://www.youtube.com/watch?v=83TiUbFY6fY", "name": "Video 5 (Manual Captions - Cached)"},
    {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "name": "Video 6 (Auto Captions - New Download)"}
]

# Set API key to mock to avoid OpenAI / Gemini billing costs and limits
API_KEY = "mock"

def run_job(video):
    print(f"\n============================================================")
    print(f"STARTING VALIDATION FOR: {video['name']}")
    print(f"URL: {video['url']}")
    print(f"============================================================")
    
    payload = {
        "url": video["url"],
        "gemini_api_key": API_KEY
    }
    
    response = requests.post(f"{BASE_URL}/api/analyze", json=payload)
    if response.status_code != 200:
        print(f"Failed to start job: {response.status_code} - {response.text}")
        return False
        
    job_id = response.json().get("job_id")
    print(f"Job ID: {job_id}")
    
    stream_url = f"{BASE_URL}/api/progress/{job_id}"
    completed = False
    success = False
    
    # Listen to progress stream
    with requests.get(stream_url, stream=True) as r:
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith("data: "):
                    json_data = json.loads(decoded[6:])
                    print(f"[{json_data.get('status')}] {json_data.get('progress')}% - {json_data.get('message')}")
                    if json_data.get("error"):
                        print(f"ERROR: {json_data.get('error')}")
                        break
                    if json_data.get("status") == "completed":
                        completed = True
                        success = True
                        break
                    if json_data.get("status") == "failed":
                        completed = True
                        success = False
                        break
                        
    if not completed or not success:
        print(f"Job {job_id} failed to complete successfully.")
        return False
        
    # Fetch clips
    clips_resp = requests.get(f"{BASE_URL}/api/clips/{job_id}")
    if clips_resp.status_code != 200:
        print(f"Failed to fetch clips: {clips_resp.text}")
        return False
        
    clips_data = clips_resp.json()
    clips = clips_data.get("clips", [])
    print(f"SUCCESS: Generated {len(clips)} clips!")
    
    # Verify each clip file exists on disk and is not 0 bytes
    for c in clips:
        filename = c["filename"]
        # The file is saved in output/{job_id}/{filename} relative to backend
        file_path = os.path.join("output", job_id, filename)
        exists = os.path.exists(file_path)
        size = os.path.getsize(file_path) if exists else 0
        print(f"  - Clip: {filename} | Exists: {exists} | Size: {size} bytes | Encoder Used: {c.get('encoder_used')}")
        if not exists or size == 0:
            print(f"  ERROR: Clip file {filename} does not exist or is empty.")
            return False
            
    return True

def main():
    print("Starting manual validation of 5 videos...")
    success_count = 0
    for video in videos_to_test:
        try:
            ok = run_job(video)
            if ok:
                success_count += 1
            # Sleep slightly between jobs
            time.sleep(2)
        except Exception as e:
            print(f"Exception during validation of {video['name']}: {e}")
            
    print(f"\n============================================================")
    print(f"VALIDATION COMPLETE: {success_count}/{len(videos_to_test)} jobs succeeded.")
    print(f"============================================================")
    sys.exit(0 if success_count == len(videos_to_test) else 1)

if __name__ == "__main__":
    main()
