from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\gif_frames\frame_001.png")
width, height = img.size
print(f"Image Size: {width}x{height}, Mode: {img.mode}")

# Check corners to see if they are transparent (Alpha = 0)
corners = [
    ("Top-Left", img.getpixel((5, 5))),
    ("Top-Right", img.getpixel((width-5, 5))),
    ("Bottom-Left", img.getpixel((5, height-5))),
    ("Bottom-Right", img.getpixel((width-5, height-5))),
    ("Center", img.getpixel((width//2, height//2)))
]
print("Corner pixels:")
for name, color in corners:
    print(f"  {name}: {color}")
