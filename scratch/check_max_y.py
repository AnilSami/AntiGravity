from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003_clean.png")
width, height = img.size

max_y = 0
min_y = height
for y in range(height):
    for x in range(width):
        r, g, b = img.getpixel((x, y))[:3]
        if r < 255 or g < 255 or b < 255:
            if y > max_y: max_y = y
            if y < min_y: min_y = y

print(f"Cleaned frame active region: min_y={min_y}, max_y={max_y}")
