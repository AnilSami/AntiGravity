from PIL import Image
from collections import Counter

img = Image.open(r"D:\Desktop\LLM\scratch\screenshots\screenshot_T1_start.png")
# Crop the region x=80..220, y=280..380
crop = img.crop((80, 280, 220, 380))

colors = []
for y in range(crop.height):
    for x in range(crop.width):
        colors.append(crop.getpixel((x, y))[:3])

counter = Counter(colors)
print("Unique colors in the overlaid region of screenshot_T1_start.png:")
for color, count in counter.most_common(10):
    print(f"  RGB {color}: {count} pixels")
