from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003.png")
width, height = img.size

# Create a small visualization image
vis_size = 300
vis = Image.new("RGB", (vis_size, vis_size), (255, 255, 255))

for y_vis in range(vis_size):
    for x_vis in range(vis_size):
        # Map back to original coordinate
        x_orig = int(x_vis * width / vis_size)
        y_orig = int(y_vis * height / vis_size)
        
        r, g, b = img.getpixel((x_orig, y_orig))[:3]
        if r < 248 or g < 248 or b < 248:
            vis.putpixel((x_vis, y_vis), (255, 0, 0)) # Red for active content

vis.save(r"D:\Desktop\LLM\scratch\frames\mask_visualization.png")
print("Saved mask_visualization.png")
