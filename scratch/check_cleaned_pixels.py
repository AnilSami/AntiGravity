from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003_clean.png")
width, height = img.size

print("Non-white pixels in the bottom region (y > 1200) of the cleaned frame:")
found = 0
for y in range(1200, height):
    for x in range(width):
        r, g, b = img.getpixel((x, y))[:3]
        if r < 255 or g < 255 or b < 255:
            found += 1
            if found <= 20:
                print(f"  y={y}, x={x}: RGB=({r}, {g}, {b})")
            
print(f"Total non-white pixels remaining: {found}")
