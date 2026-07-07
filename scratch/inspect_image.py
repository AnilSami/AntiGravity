import os
from PIL import Image

frame_path = r"D:\Desktop\LLM\scratch\frames\frame_003.png"
if not os.path.exists(frame_path):
    print("Frame not found!")
    exit()

img = Image.open(frame_path)
width, height = img.size
print(f"Image mode: {img.mode}, Size: {width}x{height}")

# Let's check pixel colors. Let's find bounding box of non-black pixels (thresholding)
# Black background is typically (0,0,0) or very close.
# Let's scan and print active region.
bbox = img.getbbox()
print(f"Bounding box of non-zero pixels: {bbox}")

# Let's count some pixel colors or scan for potential watermark text
# Watermark is often text at the bottom or top.
# Let's save a crop of the middle region to see if the watermark is there.
# Let's analyze pixel intensities along the vertical axis.
row_intensities = []
for y in range(height):
    row_sum = 0
    for x in range(width):
        r, g, b = img.getpixel((x, y))[:3]
        row_sum += (r + g + b)
    row_intensities.append(row_sum / width)

# Print rows with significant intensity
active_ranges = []
in_active = False
start_row = 0
for y, intensity in enumerate(row_intensities):
    if intensity > 1.0: # threshold of average brightness
        if not in_active:
            start_row = y
            in_active = True
    else:
        if in_active:
            active_ranges.append((start_row, y))
            in_active = False
if in_active:
    active_ranges.append((start_row, height - 1))

print(f"Active row ranges: {active_ranges}")
