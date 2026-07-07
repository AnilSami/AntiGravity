import os
import sys
import logging

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clipper import get_shot_crop_offsets, extract_clip, get_video_resolution

def test_direct():
    video_path = "test_landscape.mp4"
    if not os.path.exists(video_path):
        print(f"Error: {video_path} does not exist.")
        return
        
    print(f"Testing direct clipping on {video_path}...")
    width, height = get_video_resolution(video_path)
    print(f"Video resolution: {width}x{height}")
    
    # Check if offsets can be generated
    print("Generating crop offsets...")
    try:
        offsets = get_shot_crop_offsets(video_path, width, height, 30.0, 100)
        print(f"Successfully generated {len(offsets)} crop offsets!")
        print(f"First 10 offsets: {offsets[:10]}")
    except Exception as e:
        print(f"Failed to generate crop offsets: {e}")
        import traceback
        traceback.print_exc()
        return

    # Extract a short clip
    output_path = "test_clip_output.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)
        
    print("Extracting test clip...")
    try:
        extract_clip(video_path, 0.0, 3.0, output_path)
        print(f"Successfully extracted clip to {output_path}!")
        if os.path.exists(output_path):
            print(f"Output file size: {os.path.getsize(output_path)} bytes")
            # Clean up (Commented out so the user can inspect the output video)
            # os.remove(output_path)
        else:
            print("Error: Output file was not created.")
    except Exception as e:
        print(f"Failed to extract clip: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct()
