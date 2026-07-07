from PIL import Image
import os

img = Image.open(r"D:\Desktop\LLM\scratch\gif_frames\frame_040.png")
width, height = img.size

# Scan inside the card area
card_x1 = 420
card_y1 = 420
card_x2 = 1190
card_y2 = 770

# Let's find all pixels that are NOT the blue background (41, 23, 244) or white background (255, 255, 255)
# We will cluster them based on their X coordinates to find the columns where the elements are.
columns_with_elements = []
for x in range(card_x1, card_x2):
    has_element = False
    for y in range(card_y1, card_y2):
        r, g, b = img.getpixel((x, y))[:3]
        # If it's not background white and not card blue/indigo
        is_bg = (r >= 250 and g >= 250 and b >= 250)
        is_card_bg = (r < 60 and g < 40 and b > 200) or (r < 100 and g < 100 and b > 150)
        if not is_bg and not is_card_bg:
            has_element = True
            break
    if has_element:
        columns_with_elements.append(x)

# Group contiguous column ranges
if not columns_with_elements:
    print("No non-bg, non-card-bg elements found.")
else:
    ranges = []
    start = columns_with_elements[0]
    prev = start
    for x in columns_with_elements[1:]:
        if x - prev > 15: # Gap threshold
            ranges.append((start, prev))
            start = x
        prev = x
    ranges.append((start, prev))
    
    print("Detected elements in columns:")
    for idx, (x1, x2) in enumerate(ranges):
        # Find Y bounds for this element column
        y_pixels = []
        for x in range(x1, x2+1):
            for y in range(card_y1, card_y2):
                r, g, b = img.getpixel((x, y))[:3]
                is_bg = (r >= 250 and g >= 250 and b >= 250)
                is_card_bg = (r < 60 and g < 40 and b > 200) or (r < 100 and g < 100 and b > 150)
                if not is_bg and not is_card_bg:
                    y_pixels.append(y)
        y1 = min(y_pixels) if y_pixels else card_y1
        y2 = max(y_pixels) if y_pixels else card_y2
        print(f"  Element {idx+1}: x = {x1}..{x2} (width {x2-x1}), y = {y1}..{y2} (height {y2-y1})")
