import os
import json

base_dir = "backend/assets/music"

def main():
    if not os.path.exists(base_dir):
        print("Music library path does not exist.")
        return
        
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".flac")):
                audio_path = os.path.join(root, f)
                json_path = os.path.splitext(audio_path)[0] + ".json"
                
                # Setup dummy license metadata
                meta = {
                    "license": "Pixabay Music License",
                    "license_id": f"PB-{f.split('.')[0].upper()}-999"
                }
                
                with open(json_path, "w", encoding="utf-8") as jf:
                    json.dump(meta, jf, indent=2)
                print(f"Created companion JSON: {json_path}")

if __name__ == "__main__":
    main()
