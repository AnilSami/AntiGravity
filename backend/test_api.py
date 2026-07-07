import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
VIDEO_URL = "https://youtu.be/aAPpQC-3EyE?si=47ORAGNgShfbSdq6"
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY or "sk-proj-" in API_KEY:
    API_KEY = "mock"

def test_pipeline():
    print(f"Testing with API Key: {API_KEY[:5]}...{API_KEY[-5:] if API_KEY else ''}")
    print("Sending POST request to /api/analyze...")
    
    payload = {
        "url": VIDEO_URL,
        "gemini_api_key": API_KEY,
        "bypass_camera_qa": True,
        "force_refresh": True
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/analyze", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return
            
        data = response.json()
        job_id = data.get("job_id")
        print(f"Job started successfully! Job ID: {job_id}")
        
        # Now listen to progress via stream (we can read lines)
        print("Listening to progress stream...")
        stream_url = f"{BASE_URL}/api/progress/{job_id}"
        
        with requests.get(stream_url, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        json_data = json.loads(decoded[6:])
                        print(f"[{json_data.get('status')}] Progress: {json_data.get('progress')}% - {json_data.get('message')}")
                        if json_data.get("error"):
                            print(f"Pipeline error reported: {json_data.get('error')}")
                            break
                        if json_data.get("status") in ["completed", "failed"]:
                            break
                            
        # If completed, check clips
        print("\nChecking /api/clips...")
        clips_resp = requests.get(f"{BASE_URL}/api/clips/{job_id}")
        print(f"Clips Status: {clips_resp.status_code}")
        if clips_resp.status_code == 200:
            clips_data = clips_resp.json()
            clips = clips_data.get("clips", [])
            print(f"Found {len(clips)} clips:")
            for c in clips:
                print(f"- Title: {c['title']} ({c['start_time']}s - {c['end_time']}s)")
                print(f"  Reason: {c['reason']}")
                print(f"  Clip URL: {BASE_URL}/api/video/{job_id}/{c['filename']}")
                
                # Test the video link
                vid_resp = requests.get(f"{BASE_URL}/api/video/{job_id}/{c['filename']}", stream=True)
                print(f"  Video link HTTP Status: {vid_resp.status_code}")
        else:
            print(f"Error fetching clips: {clips_resp.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_pipeline()
