from PIL import Image
import os

img = Image.open(r"D:\Desktop\LLM\scratch\gif_frames\frame_040.png")
width, height = img.size

# Scan inside the card area, slightly inset to avoid borders
card_x1 = 440
card_y1 = 440
card_x2 = 1170
card_y2 = 750

# Find columns with pure white pixels
white_cols = []
for x in range(card_x1, card_x2):
    has_white = False
    for y in range(card_y1, card_y2):
        r, g, b = img.getpixel((x, y))[:3]
        if r >= 254 and g >= 254 and b >= 254:
            has_white = True
            break
    if has_white:
        white_cols.append(x)

if not white_cols:
    print("No white pixels found inside the inset card.")
else:
    ranges = []
    start = white_cols[0]
    prev = start
    for x in white_cols[1:]:
        if x - prev > 15:
            ranges.append((start, prev))
            start = x
        prev = x
    ranges.append((start, prev))
    
    print("Detected white elements in columns:")
    for idx, (x1, x2) in enumerate(ranges):
        y_pixels = []
        for x in range(x1, x2+1):
            for y in range(card_y1, card_y2):
                r, g, b = img.getpixel((x, y))[:3]
                if r >= 254 and g >= 254 and b >= 254:
                    y_pixels.append(y)
        y1 = min(y_pixels) if y_pixels else card_y1
        y2 = max(y_pixels) if y_pixels else card_y2
        print(f"  White Element {idx+1}: x = {x1}..{x2} (width {x2-x1}), y = {y1}..{y2} (height {y2-y1})")
