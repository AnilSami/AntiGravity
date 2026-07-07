import os
import subprocess
from PIL import Image

video_path = r"D:\Desktop\LLM\scratch\output\clips\verify_p26_direct_with_music.mp4"
output_img = os.path.abspath("test_direct_frame.png")

subprocess.run([
    "ffmpeg", "-y",
    "-ss", "1.9",
    "-i", video_path,
    "-vframes", "1",
    output_img
], capture_output=True)

if os.path.exists(output_img):
    img = Image.open(output_img)
    width, height = img.size
    print(f"Direct frame extracted: {width}x{height}")
    
    # Search for blue pixels
    found = 0
    for y in range(height):
        for x in range(width):
            r, g, b = img.getpixel((x, y))[:3]
            # Match Dribbble card color: b > 150 and b > r * 1.3 and b > g * 1.3
            if b > 150 and b > r * 1.3 and b > g * 1.3:
                found += 1
                if found <= 5:
                    print(f"Blue pixel found at x={x}, y={y}: RGB=({r}, {g}, {b})")
    print(f"Total blue pixels found: {found}")
    os.remove(output_img)
else:
    print("Failed to extract direct frame")
