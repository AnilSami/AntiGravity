from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003.png")
width, height = img.size

# Find bounds of non-white pixels
left = width
right = 0
top = height
bottom = 0

non_white_count = 0

for y in range(height):
    for x in range(width):
        r, g, b = img.getpixel((x, y))[:3]
        # If it is not white
        if r < 250 or g < 250 or b < 250:
            non_white_count += 1
            if x < left: left = x
            if x > right: right = x
            if y < top: top = y
            if y > bottom: bottom = y

print(f"Non-white pixels bounding box: ({left}, {top}, {right}, {bottom})")
print(f"Total non-white pixels: {non_white_count} ({non_white_count/(width*height)*100:.2f}%)")
