from PIL import Image

# Open frame 40 (middle of animation)
img = Image.open(r"D:\Desktop\LLM\scratch\gif_frames\frame_040.png")
img_small = img.resize((100, 40))

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

print("\n".join(result))
