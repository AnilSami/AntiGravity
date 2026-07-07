import urllib.request
import json
import time
import sys
import os
from dotenv import load_dotenv

def main():
    load_dotenv()
    # Read working OpenAI key from system env
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY is not set in environment or .env!")
        sys.exit(1)
        
    url = "http://127.0.0.1:8000/api/analyze"
    payload = {
        "url": "https://www.youtube.com/watch?v=_ZHq2rqlp0A",
        "gemini_api_key": api_key, # pass the real key
        "subtitle_style": "kinetic",
        "creator_preset": "custom",
        "num_clips": 1,
        "bypass_camera_qa": True,
        "force_refresh": True # bypass cache to run the pipeline
    }
    
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    
    try:
        print("Submitting job...")
        response = urllib.request.urlopen(req)
        res_data = json.loads(response.read().decode('utf-8'))
        job_id = res_data.get("job_id")
        print(f"Job submitted successfully. Job ID: {job_id}")
    except Exception as e:
        print(f"Failed to submit job: {e}")
        sys.exit(1)

    # Monitor job status
    status_url = f"http://127.0.0.1:8000/api/clips/{job_id}"
    print("Waiting for job to complete...")
    for i in range(120): # up to 10 minutes
        try:
            req_status = urllib.request.Request(status_url)
            resp = urllib.request.urlopen(req_status)
            clips_data = json.loads(resp.read().decode('utf-8'))
            print("\nJob completed successfully!")
            print("Response Data:")
            print(json.dumps(clips_data, indent=2))
            break
        except urllib.error.HTTPError as e:
            if e.code == 400: # Not completed yet
                # Let's fetch progress to see where we are
                progress_url = f"http://127.0.0.1:8000/api/progress/{job_id}"
                try:
                    prog_resp = urllib.request.urlopen(urllib.request.Request(progress_url))
                    prog_data = json.loads(prog_resp.read().decode('utf-8'))
                    print(f"[{i+1}/120] Progress: {prog_data.get('progress')}% - {prog_data.get('message')}")
                except Exception:
                    print(f"[{i+1}/120] Job still in progress... sleeping 5s")
                time.sleep(5)
                continue
            else:
                print(f"HTTP Error: {e.code}")
                break
        except Exception as e:
            print(f"Error checking status: {e}")
            break

if __name__ == "__main__":
    main()
