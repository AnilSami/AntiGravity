from PIL import Image

# Open the screenshot at T1
img = Image.open(r"D:\Desktop\LLM\scratch\screenshots\screenshot_T1_start.png")
# Crop the region where the Like button was overlaid (x = 40..300, y = 500..650)
crop = img.crop((40, 500, 300, 650))
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

print("ASCII art of the overlaid Like button region in screenshot_T1_start.png:")
print("\n".join(result))
