from PIL import Image
from collections import Counter

img = Image.open(r"D:\Desktop\LLM\scratch\gif_frames\frame_040.png")

# Scan the button area and list most common colors
colors = []
for y in range(450, 750):
    for x in range(450, 1150):
        colors.append(img.getpixel((x, y))[:3])

counter = Counter(colors)
print("Top 10 colors inside the button card:")
for color, count in counter.most_common(10):
    print(f"  RGB {color}: {count} pixels ({count/(300*700)*100:.2f}%)")
