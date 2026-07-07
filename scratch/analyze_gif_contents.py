from PIL import Image
import os

frames_dir = r"D:\Desktop\LLM\scratch\gif_frames"
# Let's inspect frame 40 which has the full animation active
img = Image.open(os.path.join(frames_dir, "frame_040.png"))
width, height = img.size

# We know the card is in x=420..1190, y=420..770
# Let's check color clusters in the card to see where the thumbs-up / heart / cursor is.
# We will print pixel color samples to understand where they are located.
# Let's scan y-slices at y=500, y=550, y=600, y=650, y=700 across x=420..1190.
for y in [500, 550, 600, 650, 700]:
    row_colors = []
    # segment into 10 bins
    bin_size = (1190 - 420) // 10
    for b in range(10):
        x = 420 + b * bin_size + bin_size // 2
        r, g, b_val = img.getpixel((x, y))[:3]
        # Label the color
        if r > 240 and g > 240 and b_val > 240:
            label = "White"
        elif r < 60 and g < 40 and b_val > 200:
            label = "Blue"
        elif r > 200 and g < 100 and b_val < 100:
            label = "Red/Pink"
        else:
            label = f"RGB({r},{g},{b_val})"
        row_colors.append(f"x={x}:{label}")
    print(f"y={y}: " + " | ".join(row_colors))
