from PIL import Image
import os
import subprocess

def analyze_frames():
    input_video = r"D:\Desktop\LLM\Like Button.mp4"
    temp_dir = r"D:\Desktop\LLM\scratch\click_detect_frames2"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Extract frames at 60 FPS
    print("Extracting frames...")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", input_video,
        "-vsync", "0",
        os.path.join(temp_dir, "frame_%04d.png")
    ], capture_output=True)
    
    frames = sorted([f for f in os.listdir(temp_dir) if f.endswith(".png")])
    print(f"Total extracted frames: {len(frames)}")
    
    # Let's inspect the color in the center (where the thumbs-up / heart is)
    # Usually in the center-left: around x=580..620, y=700..750 of the 1500x1500px image
    for idx in range(0, len(frames), 5):
        img = Image.open(os.path.join(temp_dir, frames[idx]))
        # Sample color at a few points
        c1 = img.getpixel((750, 750))[:3] # Exact center
        c2 = img.getpixel((580, 750))[:3] # Thumbs-up area
        c3 = img.getpixel((920, 750))[:3] # Subscribe area
        print(f"Frame {idx+1} (t={(idx)/60.0:.3f}s): Center={c1}, ThumbsUp={c2}, Sub={c3}")
        
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    analyze_frames()
