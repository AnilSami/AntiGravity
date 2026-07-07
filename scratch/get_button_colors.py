from PIL import Image
from collections import Counter

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003.png")
width, height = img.size

# Round colors to nearest 10 to group similar shades
colors = []
for y in range(height):
    for x in range(width):
        r, g, b = img.getpixel((x, y))[:3]
        # Ignore near-white pixels
        if r > 240 and g > 240 and b > 240:
            continue
        colors.append((r // 10 * 10, g // 10 * 10, b // 10 * 10))

counter = Counter(colors)
print("Top 10 most common non-white colors in the button:")
for color, count in counter.most_common(10):
    print(f"  RGB {color}: {count} pixels ({count/(width*height)*100:.2f}%)")
