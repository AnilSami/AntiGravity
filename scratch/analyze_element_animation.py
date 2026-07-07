from PIL import Image
import os

frames_dir = r"D:\Desktop\LLM\scratch\gif_frames"
frame_files = sorted([f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".png")])

print("Analyzing motion and colors inside Element 2 region (x=590..730, y=520..670):")
for step in range(0, len(frame_files), 10):
    f_name = frame_files[step]
    img = Image.open(os.path.join(frames_dir, f_name))
    
    # We will scan the region x=590..730, y=520..670 for colors
    colors_found = set()
    for y in range(520, 670):
        for x in range(590, 730):
            r, g, b = img.getpixel((x, y))[:3]
            # Categorize color
            if r > 240 and g > 240 and b > 240:
                colors_found.add("White")
            elif r > 200 and g < 100 and b < 100:
                colors_found.add("Red/Pink")
            elif r < 60 and g < 40 and b > 200:
                pass # Card blue
            else:
                # Add other prominent non-blue colors
                if abs(r - g) > 20 or abs(g - b) > 20:
                    colors_found.add(f"RGB({r},{g},{b})")
                    
    print(f"Frame {f_name}: Colors found = {sorted(list(colors_found))}")
