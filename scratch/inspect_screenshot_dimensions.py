from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\screenshots\screenshot_T1_start.png")
width, height = img.size
print(f"Screenshot size: {width}x{height}")

# Find any pixel where B is high (B > 150 and B > r and B > g)
found = 0
for y in range(height):
    for x in range(width):
        r, g, b = img.getpixel((x, y))[:3]
        if b > 150 and b > r * 1.3 and b > g * 1.3:
            found += 1
            if found <= 5:
                print(f"Found blue pixel at x={x}, y={y}: RGB=({r}, {g}, {b})")
print(f"Total blue pixels: {found}")
