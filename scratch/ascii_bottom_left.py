from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003.png")
# Crop the region x=150..750, y=1100..1400
crop = img.crop((150, 1100, 750, 1400))
img_small = crop.resize((80, 24))

# Convert to grayscale
img_gray = img_small.convert("L")

# Convert pixels to characters
chars = ["@", "#", "8", "&", "o", ":", "*", ".", " "]
result = []
for y in range(img_gray.height):
    row = []
    for x in range(img_gray.width):
        l = img_gray.getpixel((x, y))
        char_idx = min(8, int(l / 28.5))
        row.append(chars[char_idx])
    result.append("".join(row))

print("ASCII art of bottom left region:")
print("\n".join(result))
