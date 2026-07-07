import os
import sys
import time
import requests
import json
import subprocess

def run_real_pipeline():
    # 1. Get the OpenAI API key from the environment
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("[ERROR] OPENAI_API_KEY environment variable is not set. Cannot run in real mode.")
        return
        
    print(f"Using OpenAI API Key for real run: {openai_key[:8]}...{openai_key[-4:]}")
    
    # 2. Start uvicorn server as a background process
    print("Starting FastAPI server...")
    python_path = os.path.abspath("backend/venv/Scripts/python.exe")
    os.makedirs("scratch", exist_ok=True)
    server_log = open("scratch/server.log", "w")
    server_process = subprocess.Popen(
        [python_path, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd="backend",
        stdout=server_log,
        stderr=subprocess.STDOUT
    )
    
    # Wait for server to start
    time.sleep(3)
    
    BASE_URL = "http://127.0.0.1:8000"
    VIDEO_URL = "https://youtu.be/aAPpQC-3EyE?si=47ORAGNgShfbSdq6"
    
    payload = {
        "url": VIDEO_URL,
        "gemini_api_key": openai_key,
        "bypass_camera_qa": True,
        "force_refresh": True
    }
    
    try:
        # Trigger analysis
        print("Sending POST request to /api/analyze...")
        response = requests.post(f"{BASE_URL}/api/analyze", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return
            
        data = response.json()
        job_id = data.get("job_id")
        print(f"Job started successfully! Job ID: {job_id}")
        
        # Listen to progress
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
                            
        # Fetch clips info
        print("\nChecking /api/clips...")
        clips_resp = requests.get(f"{BASE_URL}/api/clips/{job_id}")
        print(f"Clips Status: {clips_resp.status_code}")
        if clips_resp.status_code == 200:
            clips_data = clips_resp.json()
            print("\n--- CLIPS DATA ---")
            print(json.dumps(clips_data, indent=2))
            
            # Save it to a file
            os.makedirs("scratch", exist_ok=True)
            with open("scratch/real_clips_output.json", "w") as f:
                json.dump(clips_data, f, indent=2)
                print("\nSaved clips output to scratch/real_clips_output.json")
        else:
            print(f"Error fetching clips: {clips_resp.text}")
            
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        print("Stopping FastAPI server...")
        server_process.terminate()
        server_process.wait()
        server_log.close()
        print("Server stopped.")

if __name__ == "__main__":
    run_real_pipeline()
