import os
import shutil
import subprocess
from PIL import Image

def process_dribbble_gif():
    print("=== Dribbble GIF Crop & Transparency Processor ===")
    
    input_gif = r"D:\Desktop\LLM\scratch\downloaded_like.gif"
    output_dir = r"D:\Desktop\LLM\assets\animations"
    output_webm = os.path.join(output_dir, "like_button.webm")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Create temp directories for frame extraction
    temp_extract_dir = r"D:\Desktop\LLM\scratch\gif_extract"
    temp_clean_dir = r"D:\Desktop\LLM\scratch\gif_clean"
    
    shutil.rmtree(temp_extract_dir, ignore_errors=True)
    shutil.rmtree(temp_clean_dir, ignore_errors=True)
    os.makedirs(temp_extract_dir, exist_ok=True)
    os.makedirs(temp_clean_dir, exist_ok=True)
    
    # 2. Extract frames at 33.33 FPS (matching the GIF frame rate)
    print("Extracting frames from GIF...")
    extract_cmd = [
        "ffmpeg", "-y",
        "-i", input_gif,
        os.path.join(temp_extract_dir, "frame_%04d.png")
    ]
    subprocess.run(extract_cmd, check=True, capture_output=True)
    
    frames = sorted([f for f in os.listdir(temp_extract_dir) if f.endswith(".png")])
    print(f"Extracted {len(frames)} frames.")
    
    # Crop dimensions (exact bounding box of the blue card banner)
    crop_x1 = 420
    crop_y1 = 420
    crop_x2 = 1190
    crop_y2 = 770
    
    W = crop_x2 - crop_x1  # 770
    H = crop_y2 - crop_y1  # 350
    R = 40  # Corner radius for rounded corners
    
    # 3. Crop and clean each frame
    print("Cropping card and applying rounded corners transparency...")
    for idx, frame_name in enumerate(frames):
        if idx % 10 == 0 or idx == len(frames) - 1:
            print(f"  Processing frame {idx+1}/{len(frames)}...")
            
        frame_path = os.path.join(temp_extract_dir, frame_name)
        img = Image.open(frame_path).convert("RGBA")
        
        # Crop to the active card region
        cropped = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        pixels = cropped.load()
        
        # Apply rounded corner mask to make outer corner pixels transparent
        for y in range(H):
            for x in range(W):
                # Check top-left corner
                if x < R and y < R:
                    if (x - R)**2 + (y - R)**2 > R**2:
                        pixels[x, y] = (255, 255, 255, 0)
                # Check top-right corner
                elif x > W - R and y < R:
                    if (x - (W - R))**2 + (y - R)**2 > R**2:
                        pixels[x, y] = (255, 255, 255, 0)
                # Check bottom-left corner
                elif x < R and y > H - R:
                    if (x - R)**2 + (y - (H - R))**2 > R**2:
                        pixels[x, y] = (255, 255, 255, 0)
                # Check bottom-right corner
                elif x > W - R and y > H - R:
                    if (x - (W - R))**2 + (y - (H - R))**2 > R**2:
                        pixels[x, y] = (255, 255, 255, 0)
                
                # Check if pixel is a white background pixel that lies on the extreme borders
                # (sometimes there is slight antialiasing artifacts at the card boundary)
                r, g, b, a = pixels[x, y]
                if r >= 253 and g >= 253 and b >= 253:
                    if x < 4 or x > W - 4 or y < 4 or y > H - 4:
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
    print(f"Cleaned transparent WebM successfully saved to: {output_webm}")
    
    # 5. Clean up temp directories
    shutil.rmtree(temp_extract_dir, ignore_errors=True)
    shutil.rmtree(temp_clean_dir, ignore_errors=True)
    print("Cleanup complete.")

if __name__ == "__main__":
    process_dribbble_gif()
