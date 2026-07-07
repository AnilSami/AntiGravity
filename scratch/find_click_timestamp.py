import os
import subprocess
from PIL import Image

def find_click():
    input_video = r"D:\Desktop\LLM\Like Button.mp4"
    temp_dir = r"D:\Desktop\LLM\scratch\click_detect_frames"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Extract frames at 60 FPS
    print("Extracting frames for click detection...")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vsync", "0",
        os.path.join(temp_dir, "frame_%04d.png")
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    
    frames = sorted([f for f in os.listdir(temp_dir) if f.endswith(".png")])
    print(f"Extracted {len(frames)} frames.")
    
    # Let's compute pixel differences between consecutive frames in the center region
    max_diff = 0
    click_frame = 0
    
    prev_img = None
    for idx, f_name in enumerate(frames):
        img_path = os.path.join(temp_dir, f_name)
        img = Image.open(img_path).convert("L")
        
        # Focus on the middle button region (center area)
        width, height = img.size
        # Crop region where the button usually resides (center)
        cropped = img.crop((width // 4, height // 4, 3 * width // 4, 3 * height // 4))
        
        if prev_img is not None:
            # Simple pixel difference
            diff = 0
            w, h = cropped.size
            p1 = cropped.load()
            p2 = prev_img.load()
            for y in range(h):
                for x in range(w):
                    diff += abs(p1[x, y] - p2[x, y])
            
            # Print frame difference info
            if diff > max_diff:
                max_diff = diff
                click_frame = idx + 1 # 1-indexed
            
            # If difference is large, it could be the click pop
            if diff > 1000000:
                print(f"Frame {idx+1}: Large difference = {diff}")
                
        prev_img = cropped

    time_offset = (click_frame - 1) / 60.0
    print(f"Maximum difference at Frame {click_frame} (offset: {time_offset:.3f}s)")
    
    # Clean up
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    find_click()
