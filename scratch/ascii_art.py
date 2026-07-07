from PIL import Image

# Open the entire frame
img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003_clean.png")
img_small = img.resize((100, 40))

# Convert to grayscale
img_gray = img_small.convert("L")

# Convert pixels to characters
# Black/colored pixels are darker (low L values), white background is 255.
chars = ["@", "#", "8", "&", "o", ":", "*", ".", " "]
result = []
for y in range(img_gray.height):
    row = []
    for x in range(img_gray.width):
        l = img_gray.getpixel((x, y))
        # Map [0, 255] to chars index [0, 8]
        char_idx = min(8, int(l / 28.5))
        row.append(chars[char_idx])
    result.append("".join(row))

print("\n".join(result))
