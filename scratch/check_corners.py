from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003.png")
# Check corners
corners = [
    ("Top-Left", img.getpixel((10, 10))),
    ("Top-Right", img.getpixel((1490, 10))),
    ("Bottom-Left", img.getpixel((10, 1490))),
    ("Bottom-Right", img.getpixel((1490, 1490))),
    ("Center", img.getpixel((750, 750)))
]
print("Corner pixels:")
for name, color in corners:
    print(f"  {name}: {color}")
