from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003.png")
# Let's inspect rows around y=1250, x=212..696
watermark_pixels = []
for x in range(212, 696):
    color = img.getpixel((x, 1250))[:3]
    # If not pure white
    if color != (255, 255, 255):
        watermark_pixels.append((x, color))

print(f"Total non-white pixels on row 1250: {len(watermark_pixels)}")
print("First 15 non-white pixels:")
for x, c in watermark_pixels[:15]:
    print(f"  x={x}: RGB={c}")
