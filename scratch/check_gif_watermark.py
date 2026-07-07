from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\gif_frames\frame_040.png")
width, height = img.size

# Scan for non-white pixels
left = width
right = 0
top = height
bottom = 0
active_pixels = 0

for y in range(height):
    for x in range(width):
        r, g, b = img.getpixel((x, y))[:3]
        if r < 250 or g < 250 or b < 250:
            active_pixels += 1
            if x < left: left = x
            if x > right: right = x
            if y < top: top = y
            if y > bottom: bottom = y

print(f"GIF frame 40 active region: ({left}, {top}, {right}, {bottom})")
print(f"Total active pixels: {active_pixels} ({active_pixels/(width*height)*100:.2f}%)")
