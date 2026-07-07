from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003.png")
width, height = img.size

# We will scan horizontal bands of 100 pixels height and print their bounding boxes
for band_idx in range(15):
    y_start = band_idx * 100
    y_end = y_start + 100
    
    # Find bounding box within this band
    left = width
    right = 0
    band_active = False
    
    for y in range(y_start, y_end):
        for x in range(width):
            r, g, b = img.getpixel((x, y))[:3]
            if r < 250 or g < 250 or b < 250:
                band_active = True
                if x < left: left = x
                if x > right: right = x
                
    if band_active:
        print(f"Band {y_start:4d}-{y_end:4d}: Active X range = ({left:4d}, {right:4d})")
