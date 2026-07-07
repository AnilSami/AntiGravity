import os
import subprocess
from PIL import Image

output_img = os.path.abspath("test_frame.png")
subprocess.run([
    "ffmpeg", "-y",
    "-ss", "1.9",
    "-i", "test_overlay_run.mp4",
    "-vframes", "1",
    output_img
], capture_output=True)

if os.path.exists(output_img):
    img = Image.open(output_img)
    width, height = img.size
    print(f"Frame extracted: {width}x{height}")
    
    # Search for blue pixels
    found = 0
    for y in range(height):
        for x in range(width):
            r, g, b = img.getpixel((x, y))[:3]
            if b > 180 and b > r * 2 and b > g * 2:
                found += 1
                if found <= 5:
                    print(f"Blue pixel found at x={x}, y={y}: RGB=({r}, {g}, {b})")
    print(f"Total blue pixels: {found}")
    
    # Cleanup
    os.remove(output_img)
else:
    print("Failed to extract frame")
