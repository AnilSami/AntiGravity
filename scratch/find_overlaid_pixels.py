from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\screenshots\screenshot_T1_start.png")
width, height = img.size

# Search for any blue-ish pixels where B is much higher than R and G
# The button card has RGB around (41, 23, 244) or similar.
found_pixels = []
for y in range(height):
    for x in range(width):
        r, g, b = img.getpixel((x, y))[:3]
        # Look for vibrant blue/indigo
        if b > 180 and b > r * 2 and b > g * 2:
            found_pixels.append((x, y, (r, g, b)))
            if len(found_pixels) <= 15:
                print(f"Found blue pixel at x={x}, y={y}: RGB=({r}, {g}, {b})")

print(f"Total blue/indigo pixels found: {len(found_pixels)}")
