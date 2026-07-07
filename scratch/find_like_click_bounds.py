from PIL import Image
import os

frames_dir = r"D:\Desktop\LLM\scratch\gif_frames"
frame_files = sorted([f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".png")])

# Scan region around the heart: x=530..750, y=470..700 across frames 30 to 65
left = 1600
right = 0
top = 1200
bottom = 0

for f_idx in range(len(frame_files)):
    img = Image.open(os.path.join(frames_dir, frame_files[f_idx]))
    for y in range(400, 800):
        for x in range(480, 800):
            r, g, b = img.getpixel((x, y))[:3]
            is_bg = (r >= 250 and g >= 250 and b >= 250)
            is_card_bg = (r < 60 and g < 40 and b > 200) or (r < 100 and g < 100 and b > 150)
            if not is_bg and not is_card_bg:
                if x < left: left = x
                if x > right: right = x
                if y < top: top = y
                if y > bottom: bottom = y

print(f"Bounding box of the Like click action (frames 30-65):")
print(f"  x1={left}, y1={top}, x2={right}, y2={bottom}")
print(f"  width={right-left}, height={bottom-top}")
