import os
import shutil
import subprocess
from PIL import Image

def extract_isolated_like():
    print("=== Dribbble Isolated Like Button Processor ===")
    
    input_gif = r"D:\Desktop\LLM\scratch\downloaded_like.gif"
    output_dir = r"D:\Desktop\LLM\assets\animations"
    output_webm = os.path.join(output_dir, "like_button.webm")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Create temp directories for frame extraction
    temp_extract_dir = r"D:\Desktop\LLM\scratch\isolated_extract"
    temp_clean_dir = r"D:\Desktop\LLM\scratch\isolated_clean"
    
    shutil.rmtree(temp_extract_dir, ignore_errors=True)
    shutil.rmtree(temp_clean_dir, ignore_errors=True)
    os.makedirs(temp_extract_dir, exist_ok=True)
    os.makedirs(temp_clean_dir, exist_ok=True)
    
    # 2. Extract frames at 33.33 FPS
    print("Extracting frames from GIF...")
    extract_cmd = [
        "ffmpeg", "-y",
        "-i", input_gif,
        os.path.join(temp_extract_dir, "frame_%04d.png")
    ]
    subprocess.run(extract_cmd, check=True, capture_output=True)
    
    frames = sorted([f for f in os.listdir(temp_extract_dir) if f.endswith(".png")])
    print(f"Extracted {len(frames)} frames.")
    
    # Crop bounds for ONLY the heart, click animation, and cursor
    crop_x1 = 510
    crop_y1 = 450
    crop_x2 = 760
    crop_y2 = 720
    
    W = crop_x2 - crop_x1  # 250
    H = crop_y2 - crop_y1  # 270
    
    # 3. Clean each frame to isolate the heart and clicking action
    print("Isolating Like button and making card background transparent...")
    for idx, frame_name in enumerate(frames):
        if idx % 10 == 0 or idx == len(frames) - 1:
            print(f"  Processing frame {idx+1}/{len(frames)}...")
            
        frame_path = os.path.join(temp_extract_dir, frame_name)
        img = Image.open(frame_path).convert("RGBA")
        
        # Crop to the Like region
        cropped = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        pixels = cropped.load()
        
        for y in range(H):
            for x in range(W):
                r, g, b, a = pixels[x, y]
                
                # Check for white canvas background
                is_canvas_bg = (r >= 250 and g >= 250 and b >= 250)
                
                # Check for blue/indigo card background or card shadow
                # Blue background typically has high B, low R, low G.
                # Shadow typically has lower brightness but B remains dominant.
                is_card_blue = False
                if b > 120:
                    # Blue is dominant
                    if b > r * 1.25 and b > g * 1.25:
                        is_card_blue = True
                
                if is_canvas_bg or is_card_blue:
                    # Make it completely transparent
                    pixels[x, y] = (255, 255, 255, 0)
                    
        clean_path = os.path.join(temp_clean_dir, frame_name)
        cropped.save(clean_path)
        
    # 4. Reassemble frames into a 33.33 FPS transparent WebM (VP9) video
    print("Reassembling cropped frames into transparent WebM (VP9)...")
    assemble_cmd = [
        "ffmpeg", "-y",
        "-r", "33.33",
        "-i", os.path.join(temp_clean_dir, "frame_%04d.png"),
        "-c:v", "libvpx-vp9",
        "-pix_fmt", "yuva420p",
        "-lossless", "1",
        output_webm
    ]
    subprocess.run(assemble_cmd, check=True, capture_output=True)
    print(f"Cleaned isolated Like WebM successfully saved to: {output_webm}")
    
    # 5. Clean up temp directories
    shutil.rmtree(temp_extract_dir, ignore_errors=True)
    shutil.rmtree(temp_clean_dir, ignore_errors=True)
    print("Cleanup complete.")

if __name__ == "__main__":
    extract_isolated_like()
