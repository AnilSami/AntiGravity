from PIL import Image
import os

frames_dir = r"D:\Desktop\LLM\scratch\gif_frames"
frame_files = sorted([f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".png")])

for step in range(0, len(frame_files), 10):
    f_name = frame_files[step]
    img = Image.open(os.path.join(frames_dir, f_name))
    width, height = img.size
    
    left = width
    right = 0
    top = height
    bottom = 0
    active_pixels = 0
    
    for y in range(height):
        for x in range(width):
            r, g, b = img.getpixel((x, y))[:3]
            if r < 252 or g < 252 or b < 252:
                active_pixels += 1
                if x < left: left = x
                if x > right: right = x
                if y < top: top = y
                if y > bottom: bottom = y
                
    print(f"Frame {f_name}: Bounding Box = ({left}, {top}, {right}, {bottom}), Active pixels = {active_pixels}")
