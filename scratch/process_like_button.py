import os
import shutil
import subprocess
from PIL import Image

def process_video():
    print("=== Watermark Removal Processor ===")
    
    input_video = r"D:\Desktop\LLM\Like Button.mp4"
    output_dir = r"D:\Desktop\LLM\assets\animations"
    output_video = os.path.join(output_dir, "like_button.mp4")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Create temp directories for frame extraction
    temp_extract_dir = r"D:\Desktop\LLM\scratch\extracted_frames"
    temp_clean_dir = r"D:\Desktop\LLM\scratch\cleaned_frames"
    
    shutil.rmtree(temp_extract_dir, ignore_errors=True)
    shutil.rmtree(temp_clean_dir, ignore_errors=True)
    os.makedirs(temp_extract_dir, exist_ok=True)
    os.makedirs(temp_clean_dir, exist_ok=True)
    
    # 2. Extract frames at 60 fps
    print("Extracting frames from input video at 60 FPS...")
    extract_cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vsync", "0",
        os.path.join(temp_extract_dir, "frame_%04d.png")
    ]
    subprocess.run(extract_cmd, check=True, capture_output=True)
    
    frames = sorted([f for f in os.listdir(temp_extract_dir) if f.endswith(".png")])
    print(f"Extracted {len(frames)} frames.")
    
    # 3. Clean each frame
    print("Cleaning watermarks from frames...")
    for idx, frame_name in enumerate(frames):
        if idx % 10 == 0 or idx == len(frames) - 1:
            print(f"  Processing frame {idx+1}/{len(frames)}...")
            
        frame_path = os.path.join(temp_extract_dir, frame_name)
        img = Image.open(frame_path)
        width, height = img.size
        
        # Fast pixel operations
        pixels = img.load()
        
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y][:3]
                
                # Check for white background or green watermark
                is_bg = (r >= 250 and g >= 250 and b >= 250)
                is_watermark = False
                
                if r > 185 and g > 230 and b > 185:
                    # Light green watermark
                    if g - r > 8 and g - b > 8:
                        is_watermark = True
                    # Light gray watermark
                    elif abs(r - g) < 15 and abs(g - b) < 15 and abs(r - b) < 15:
                        is_watermark = True
                        
                if is_bg or is_watermark:
                    pixels[x, y] = (255, 255, 255)
                    
        clean_path = os.path.join(temp_clean_dir, frame_name)
        img.save(clean_path)
        
    # 4. Reassemble frames into a 60 FPS H.264 MP4 video
    print("Reassembling cleaned frames into video...")
    assemble_cmd = [
        "ffmpeg", "-y",
        "-r", "60",
        "-i", os.path.join(temp_clean_dir, "frame_%04d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        output_video
    ]
    subprocess.run(assemble_cmd, check=True, capture_output=True)
    print(f"Cleaned video successfully saved to: {output_video}")
    
    # 5. Clean up temp directories
    shutil.rmtree(temp_extract_dir, ignore_errors=True)
    shutil.rmtree(temp_clean_dir, ignore_errors=True)
    print("Cleanup complete.")

if __name__ == "__main__":
    process_video()
