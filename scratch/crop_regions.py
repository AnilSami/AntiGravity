from PIL import Image

img = Image.open(r"D:\Desktop\LLM\scratch\frames\frame_003.png")

# Crop A: Left edge suspicious area
crop_a = img.crop((0, 800, 250, 1050))
crop_a.save(r"D:\Desktop\LLM\scratch\frames\crop_left_edge.png")

# Crop B: Bottom-right/other corners to check
crop_b = img.crop((0, 0, 1500, 1500))
# Let's write a script to check if there is text by checking connected components.
print("Cropped left edge suspicious area to D:\\Desktop\\LLM\\scratch\\frames\\crop_left_edge.png")
