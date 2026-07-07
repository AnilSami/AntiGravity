import os
import sys
import logging
from collections import namedtuple

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("generate_comparison")

# Add backend directory to system path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from job_manager import generate_ass
from clipper import extract_clip, check_ffmpeg

def main():
    if not check_ffmpeg():
        logger.error("ffmpeg is not installed or not in PATH.")
        sys.exit(1)

    input_video = os.path.join(backend_dir, "scratch_video", "temp_30s.mp4")
    if not os.path.exists(input_video):
        logger.error(f"Input video not found: {input_video}")
        sys.exit(1)

    logger.info("Initializing comparison video generator...")

    # Mock transcript to demonstrate all semantic colors:
    # - "Sam Altman" / "OpenAI" / "artificial intelligence" / "$10 million" -> Atomic phrases
    # - "$10 million" -> Green number
    # - "startup" -> Orange keyword
    # - "why" -> Cyan question word
    TranscriptEntry = namedtuple("TranscriptEntry", ["text", "start", "duration"])
    transcript_list = [
        TranscriptEntry("This is Sam Altman from OpenAI", 0.2, 2.3),
        TranscriptEntry("and we just built artificial intelligence", 2.6, 2.9),
        TranscriptEntry("that makes $10 million in revenue", 5.6, 2.2),
        TranscriptEntry("why are you not starting a startup today?", 7.9, 2.0)
    ]

    styles = ["classic", "kinetic", "karaoke", "auto"]
    output_files = {}

    for style in styles:
        logger.info(f"--- Generating comparison video for style: {style} ---")
        
        ass_path = os.path.join(backend_dir, f"comparison_{style}.ass")
        output_path = os.path.join(backend_dir, f"{style}.mp4")

        # Clean old files
        if os.path.exists(ass_path):
            os.remove(ass_path)
        if os.path.exists(output_path):
            os.remove(output_path)

        # 1. Generate subtitle ASS file
        generate_ass(
            transcript_list=transcript_list,
            start_time=0.0,
            end_time=10.0,
            ass_path=ass_path,
            subtitle_style=style,
            font_name="Anton",
            font_size=75,
            pop_scale=1.18,
            pop_duration=260,
            primary_color="#FFFFFF",
            highlight_color="#FFD400",
            outline_color="#000000",
            outline_thickness=4,
            shadow_depth=2
        )

        # 2. Extract clip and burn subtitles
        try:
            metadata = {}
            extract_clip(
                input_path=input_video,
                start=0.0,
                end=10.0,
                output_path=output_path,
                srt_path=ass_path,
                metadata=metadata
            )
            logger.info(f"Successfully generated comparison: {output_path}")
            logger.info(f"Metadata captured: {metadata}")
            output_files[style] = output_path
        except Exception as e:
            logger.error(f"Failed to generate comparison video for style {style}: {e}")

        # Clean up temporary ASS file
        if os.path.exists(ass_path):
            try:
                os.remove(ass_path)
            except Exception:
                pass

    logger.info("Comparison generation completed!")
    for style, path in output_files.items():
        logger.info(f"  - {style}: {path} ({os.path.getsize(path)} bytes)")

if __name__ == "__main__":
    main()
