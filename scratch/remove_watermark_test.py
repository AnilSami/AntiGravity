from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003.png")
width, height = img.size

out = Image.new("RGB", (width, height), (255, 255, 255))

for y in range(height):
    for x in range(width):
        r, g, b = img.getpixel((x, y))[:3]
        
        # Rule to identify watermark / white background:
        # 1. Pure white background
        is_bg = (r >= 250 and g >= 250 and b >= 250)
        
        # 2. Light green/gray watermark on the background
        # Typically G is high, and R/B are also high but slightly lower.
        is_watermark = False
        if r > 190 and g > 235 and b > 190:
            # Check if it's a light green tint (G is slightly higher than R and B)
            if g - r > 10 and g - b > 10:
                is_watermark = True
            # Also light gray watermark
            elif abs(r - g) < 15 and abs(g - b) < 15 and abs(r - b) < 15:
                is_watermark = True
                
        if is_bg or is_watermark:
            out.putpixel((x, y), (255, 255, 255))
        else:
            out.putpixel((x, y), (r, g, b))

out.save(r"D:\Desktop\LLM\scratch\frames\frame_003_clean.png")
print("Saved frame_003_clean.png")
