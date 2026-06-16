import os
import uuid
import logging
import asyncio
from typing import List, Dict, Optional
from pydantic import BaseModel

from analyzer import get_video_id, fetch_transcript_list, analyze_with_gemini
from clipper import download_video, extract_clip, check_ffmpeg
import re

logger = logging.getLogger("job_manager")


EMOJI_DICTIONARY = {
    "CEO": "💼",
    "AI": "🤖",
    "robot": "🤖",
    "smart": "🧠",
    "brain": "🧠",
    "mind": "🧠",
    "learn": "📚",
    "learning": "📚",
    "data": "📊",
    "money": "💵",
    "cash": "💵",
    "dollar": "💵",
    "profit": "💰",
    "rich": "💰",
    "wealth": "💰",
    "jobs": "💼",
    "job": "💼",
    "work": "💼",
    "career": "💼",
    "life": "🌎",
    "world": "🌎",
    "global": "🌎",
    "love": "❤️",
    "happy": "😊",
    "laugh": "😂",
    "funny": "😂",
    "crypto": "🪙",
    "bitcoin": "🪙",
    "blockchain": "🪙",
    "computer": "💻",
    "code": "💻",
    "coding": "💻",
    "tech": "💻",
    "software": "💻",
    "science": "🔬",
    "research": "🔬",
    "rocket": "🚀",
    "space": "🚀",
    "launch": "🚀",
    "startup": "🚀",
    "time": "⏱️",
    "speed": "⚡",
    "fast": "⚡",
    "power": "⚡",
    "future": "🔮",
    "vision": "🔮",
    "success": "📈",
    "growth": "📈",
    "revenue": "📈",
    "fail": "📉",
    "loss": "📉",
    "crash": "📉",
    "business": "👔",
    "company": "🏢",
    "office": "🏢",
    "people": "👥",
    "team": "👥",
    "human": "👤",
    "music": "🎵",
    "song": "🎵",
    "idea": "💡",
    "innovation": "💡",
    "think": "🤔",
    "question": "❓",
    "warning": "⚠️",
    "danger": "⚠️",
    "risk": "⚠️",
    "health": "🏥",
    "medical": "🏥",
    "heart": "❤️",
    "fire": "🔥",
    "hot": "🔥",
    "viral": "🔥",
    "war": "⚔️",
    "fight": "⚔️",
    "government": "🏛️",
    "law": "⚖️",
    "justice": "⚖️",
    "automation": "🤖",
    "energy": "⚡",
    "climate": "🌡️",
    "environment": "🌿",
    "nature": "🌿",
    "food": "🍕",
    "eat": "🍕",
    "water": "💧",
    "book": "📚",
    "read": "📚",
    "write": "✍️",
    "speak": "🎤",
    "talk": "🎤",
    "interview": "🎤",
    "win": "🏆",
    "champion": "🏆",
    "award": "🏆",
    "game": "🎮",
    "play": "🎮",
    "art": "🎨",
    "design": "🎨",
    "phone": "📱",
    "mobile": "📱",
    "app": "📱",
    "internet": "🌐",
    "web": "🌐",
    "network": "🌐",
    "security": "🔒",
    "hack": "🔓",
    "privacy": "🔒",
    "secret": "🤫",
    "truth": "💯",
    "fact": "💯",
    "real": "💯",
}

# Number of words per subtitle chunk shown on screen at once
SUBTITLE_CHUNK_SIZE = 2

# Subtitle delay shift in seconds to align subtitles with audio
SUBTITLE_DELAY = 0.25


def format_ass_time(seconds: float) -> str:
    """Formats float seconds into ASS timestamp format: H:MM:SS.cc"""
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int(round((seconds - int(seconds)) * 100))
    if centiseconds >= 100:
        centiseconds = 99
    return f"{hrs:d}:{mins:02d}:{secs:02d}.{centiseconds:02d}"

def generate_ass(transcript_list, start_time: float, end_time: float, ass_path: str):
    """Generates a styled ASS subtitle file with rapid word-by-word chunks, yellow highlights, and zero time overlaps."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,75,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,10,10,800,1
"""
    # FontSize 55 is clean for 1080x1920 resolution.
    # Alignment 2 is bottom center. MarginV 280 sits it nicely in the lower-middle portion.
    # PrimaryColour is White (&H00FFFFFF), Outline is black with thickness 3 (Outline=3).

    events = [
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    # Extract all words from overlapping entries with corrected times
    words_list = []
    
    for idx, entry in enumerate(transcript_list):
        entry_start = entry.start
        entry_duration = entry.duration
        entry_end = entry_start + entry_duration
        
        # Check if transcript line overlaps with clip timeline
        if entry_start < end_time and entry_end > start_time:
            text = entry.text.strip().replace('\n', ' ')
            words = text.split()
            if not words:
                continue
            
            # Determine interval end to avoid overlap with next entry's start
            next_start = entry_end
            if idx + 1 < len(transcript_list):
                next_start = transcript_list[idx+1].start
                
            # Spoken duration
            interval_end = min(entry_end, next_start)
            if interval_end <= entry_start or interval_end - entry_start < 0.5:
                interval_end = entry_end
                
            spoken_duration = interval_end - entry_start
            word_dur = spoken_duration / len(words)
            
            for i, word in enumerate(words):
                w_start = entry_start + i * word_dur + SUBTITLE_DELAY
                w_end = entry_start + (i + 1) * word_dur + SUBTITLE_DELAY
                
                # Check if word falls in the clip timeline
                if w_start < end_time and w_end > start_time:
                    words_list.append({
                        "text": word,
                        "start": w_start,
                        "end": w_end
                    })
                    
    # Sort all words by start time to guarantee correct chronology
    words_list.sort(key=lambda x: x["start"])
    
    # Chunk words dynamically (split chunk on: word count >= 3, punctuation ['.', ',', '?', '!', ';', ':'], time gap to next word > 0.35s, or duration > 1.5s)
    dynamic_word_chunks = []
    current_chunk = []
    
    for w in words_list:
        if not current_chunk:
            current_chunk.append(w)
        else:
            prev_word = current_chunk[-1]
            first_word = current_chunk[0]
            
            cond_word_count = len(current_chunk) >= 3
            
            prev_text_clean = prev_word["text"].strip()
            cond_punctuation = bool(prev_text_clean and prev_text_clean[-1] in ['.', ',', '?', '!', ';', ':'])
            
            cond_time_gap = (w["start"] - prev_word["end"]) > 0.35
            
            cond_duration = (w["end"] - first_word["start"]) > 1.5
            
            if cond_word_count or cond_punctuation or cond_time_gap or cond_duration:
                dynamic_word_chunks.append(current_chunk)
                current_chunk = [w]
            else:
                current_chunk.append(w)
                
    if current_chunk:
        dynamic_word_chunks.append(current_chunk)
        
    raw_chunks = []
    for chunk_words in dynamic_word_chunks:
        # Apply style and emoji mapping
        emoji_suffix = ""
        for w in chunk_words:
            clean_word = re.sub(r'[^\w]', '', w["text"]).lower()
            if clean_word in EMOJI_DICTIONARY:
                emoji_suffix += " " + EMOJI_DICTIONARY[clean_word]
                
        # Highlight first word in yellow
        if len(chunk_words) == 1:
            styled_text = f"{{\\c&H0000FFFF&}}{chunk_words[0]['text'].upper()}{{\\c&H00FFFFFF&}}"
        else:
            rest_text = " ".join(w['text'].upper() for w in chunk_words[1:])
            styled_text = f"{{\\c&H0000FFFF&}}{chunk_words[0]['text'].upper()}{{\\c&H00FFFFFF&}} {rest_text}"
            
        if emoji_suffix:
            styled_text += emoji_suffix
            
        c_start = max(0.0, chunk_words[0]["start"] - start_time)
        c_end = min(end_time - start_time, chunk_words[-1]["end"] - start_time)
        
        if c_end - c_start > 0.05:
            raw_chunks.append({
                "start": c_start,
                "end": c_end,
                "text": styled_text
            })

    # Resolve overlaps between chunks: ensure no chunk starts before the previous one ends
    resolved_chunks = []
    for i in range(len(raw_chunks)):
        curr = raw_chunks[i]
        start = curr["start"]
        end = curr["end"]
        
        if i + 1 < len(raw_chunks):
            next_start = raw_chunks[i+1]["start"]
            if next_start <= start:
                next_start = start + 0.1
                raw_chunks[i+1]["start"] = next_start
            
            if end > next_start:
                end = next_start
                
        if end - start > 0.05:
            resolved_chunks.append({
                "start": start,
                "end": end,
                "text": curr["text"]
            })

    for chunk in resolved_chunks:
        start_str = format_ass_time(chunk["start"])
        end_str = format_ass_time(chunk["end"])
        events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{chunk['text']}")
                    
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n" + "\n".join(events))


class ClipInfo(BaseModel):
    id: str
    title: str
    reason: str
    start_time: float
    end_time: float
    duration: float
    filename: str
    shorts_title: str
    shorts_description: str
    shorts_tags: List[str]

class JobStatus(BaseModel):
    id: str
    status: str  # "pending", "fetching_transcript", "analyzing", "downloading", "clipping", "completed", "failed"
    progress: int  # 0-100
    message: str
    error: Optional[str] = None
    clips: List[ClipInfo] = []
    created_at: float = 0.0

# In-memory store for background job progress
jobs: Dict[str, JobStatus] = {}

async def run_pipeline(job_id: str, url: str, api_key: str, num_clips: int = 5):
    """Executes the full video analysis and clipping pipeline."""
    job = jobs[job_id]
    download_dir = os.path.join("output", job_id)
    os.makedirs(download_dir, exist_ok=True)
    
    try:
        # Check ffmpeg first
        if not check_ffmpeg():
            raise RuntimeError("ffmpeg is not installed or not in PATH on this system. Clip extraction is not possible.")

        loop = asyncio.get_running_loop()
        
        # Step 1: Fetch Transcript
        job.status = "fetching_transcript"
        job.progress = 10
        job.message = "Extracting video ID and fetching transcript from YouTube..."
        video_id = get_video_id(url)
        raw_transcript = await loop.run_in_executor(None, fetch_transcript_list, video_id)
        
        # Format transcript text with precise index and float timestamps for Gemini
        formatted_lines = []
        for idx, entry in enumerate(raw_transcript):
            start = entry.start
            end = entry.start + entry.duration
            timestamp = f"[{start:.2f} - {end:.2f}]"
            text = entry.text.replace('\n', ' ')
            formatted_lines.append(f"[{idx}] {timestamp} {text}")
        transcript_text = "\n".join(formatted_lines)
        
        # Step 2: Analyze with Gemini
        job.status = "analyzing"
        job.progress = 30
        job.message = "Analyzing transcript with Gemini AI to identify interesting moments..."
        clips_data = await loop.run_in_executor(
            None, 
            analyze_with_gemini, 
            transcript_text, 
            raw_transcript,
            api_key, 
            num_clips
        )
        
        if not clips_data:
            raise ValueError("Gemini AI did not identify any key moments in the transcript.")
            
        # Step 3: Download Video
        job.status = "downloading"
        job.progress = 50
        job.message = "Downloading video from YouTube..."
        
        def on_download_progress(pct):
            def update():
                job.progress = 50 + int(pct * 0.2)  # maps 0-100 download percent to 50-70 job progress
                job.message = f"Downloading video from YouTube... {pct}%"
            loop.call_soon_threadsafe(update)
            
        video_path = await loop.run_in_executor(None, download_video, url, download_dir, on_download_progress)
        
        # Step 4: Extract clips
        job.status = "clipping"
        job.progress = 75
        job.message = "Extracting clips with ffmpeg..."
        
        # Reuses raw_transcript from Step 1
        clips = []
        for i, clip_data in enumerate(clips_data):
            clip_id = str(uuid.uuid4())[:8]
            job.message = f"Extracting clip {i+1} of {len(clips_data)}: {clip_data['title']}"
            job.progress = 75 + int((i / len(clips_data)) * 20)
            
            output_filename = f"clip_{clip_id}.mp4"
            output_path = os.path.join(download_dir, output_filename)
            
            # Generate ASS subtitle file
            ass_path = os.path.join(download_dir, f"sub_{clip_id}.ass")
            generate_ass(raw_transcript, clip_data['start_time'], clip_data['end_time'], ass_path)
            
            await loop.run_in_executor(
                None, 
                extract_clip, 
                video_path, 
                clip_data['start_time'], 
                clip_data['end_time'], 
                output_path,
                ass_path
            )
            
            duration = clip_data['end_time'] - clip_data['start_time']
            clips.append(ClipInfo(
                id=clip_id,
                title=clip_data['title'],
                reason=clip_data['reason'],
                start_time=clip_data['start_time'],
                end_time=clip_data['end_time'],
                duration=duration,
                filename=output_filename,
                shorts_title=clip_data['shorts_title'],
                shorts_description=clip_data['shorts_description'],
                shorts_tags=clip_data['shorts_tags']
            ))
            
        # Delete source video to save space
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
        except Exception as e:
            logger.warning(f"Could not remove source video file {video_path}: {e}")
            
        job.clips = clips
        job.status = "completed"
        job.progress = 100
        job.message = f"Successfully extracted {len(clips)} clips!"
        
    except Exception as e:
        logger.exception(f"Error during job processing: {job_id}")
        job.status = "failed"
        job.progress = 100
        job.message = f"Error: {str(e)}"
        job.error = str(e)
