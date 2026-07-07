import os
import logging
import asyncio
import time
from typing import List, Dict, Optional
from pydantic import BaseModel

from analyzer import get_video_id, fetch_transcript_list, analyze_with_gemini, check_youtube_availability
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
SUBTITLE_DELAY = 0.05


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

def hex_to_ass_color(hex_str: str) -> str:
    """Converts #RRGGBB to ASS BGR format &H00BBGGRR&."""
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 6:
        r = hex_str[0:2]
        g = hex_str[2:4]
        b = hex_str[4:6]
        return f"&H00{b}{g}{r}&"
    return "&H00FFFFFF&"


def generate_ass(
    transcript_list, 
    start_time: float, 
    end_time: float, 
    ass_path: str,
    subtitle_style: str = "kinetic",
    font_name: str = "Anton",
    font_size: int = 75,
    pop_scale: float = 1.18,
    pop_duration: int = 260,
    primary_color: str = "#FFFFFF",
    highlight_color: str = "#FFD400",
    outline_color: str = "#000000",
    outline_thickness: int = 4,
    shadow_depth: int = 2
) -> dict:
    """
    Generates a vertical mobile-optimized ASS subtitle file supporting:
    - Classic, Kinetic, and Karaoke modes
    - Dynamic line breaking (max 18-22 chars, balanced lines, atomic phrase protection)
    - Semantic color highlighting (Orange keywords, Green numbers, Cyan questions, Yellow active)
    - Opacity-pop easing animations
    - 100ms timing offset and 250ms punctuation hold
    - Safe Mode fallback and density limits
    """
    logger.info(f"Subtitles: Generating ASS file with style: {subtitle_style}, font: {font_name}")
    
    t_start_gen = time.perf_counter()
    
    # We wrap the main logic in a try-except to support Safe Mode fallback
    fallback_used = False
    resolved_style = subtitle_style
    
    # 2. Extract words
    words_list = []
    try:
        # Resolve colors to ASS format
        primary_color_ass = hex_to_ass_color(primary_color)
        highlight_color_ass = hex_to_ass_color(highlight_color)
        outline_color_ass = hex_to_ass_color(outline_color)
        back_color_ass = "&H8C000000&" # 55% transparent black
        
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color_ass},&H0000FFFF&,{outline_color_ass},{back_color_ass},-1,0,0,0,100,100,0,0,1,{outline_thickness},{shadow_depth},2,10,10,450,1
"""

        events = [
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        if not transcript_list:
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(header + "\n" + "\n".join(events))
            return {
                "ass_event_count": 0,
                "fallback_used": False,
                "highlight_count": 0,
                "emphasis_count": 0,
                "words_per_chunk": 0.0,
                "reading_speed": 0.0,
                "subtitle_style": subtitle_style
            }

        for idx, entry in enumerate(transcript_list):
            entry_start = entry.start
            entry_duration = entry.duration
            entry_end = entry_start + entry_duration
            
            if entry_start < end_time and entry_end > start_time:
                text = entry.text.strip().replace('\n', ' ')
                words = text.split()
                if not words:
                    continue
                    
                next_start = entry_end
                if idx + 1 < len(transcript_list):
                    next_start = transcript_list[idx+1].start
                    
                spoken_duration = min(entry_end, next_start) - entry_start
                if spoken_duration <= 0 or spoken_duration < 0.5:
                    spoken_duration = entry_duration
                    
                word_dur = spoken_duration / len(words)
                for i, word in enumerate(words):
                    w_start = entry_start + i * word_dur + SUBTITLE_DELAY
                    w_end = entry_start + (i + 1) * word_dur + SUBTITLE_DELAY
                    
                    if w_start < end_time and w_end > start_time:
                        words_list.append({
                            "text": word,
                            "start": w_start,
                            "end": w_end
                        })
                        
        words_list.sort(key=lambda x: x["start"])
        
        # Dynamic Phrase Grouping (Pause, Punctuation, WPM, and Count bounds)
        SENTENCE_ENDINGS = {'.', '?', '!'}
        dynamic_word_chunks = []
        current_chunk = []
        
        for w in words_list:
            if not current_chunk:
                current_chunk.append(w)
            else:
                prev_word = current_chunk[-1]
                first_word = current_chunk[0]
                
                # Split conditions
                cond_word_count = len(current_chunk) >= 4
                prev_text_clean = prev_word["text"].strip()
                cond_punctuation = bool(prev_text_clean and prev_text_clean[-1] in ['.', ',', '?', '!', ';', ':'])
                cond_time_gap = (w["start"] - prev_word["end"]) > 0.35
                cond_duration = (w["end"] - first_word["start"]) > 3.0
                
                # WPM check
                dur = w["end"] - first_word["start"]
                wpm = (len(current_chunk) + 1) / max(0.1, dur) * 60
                cond_wpm = wpm > 260 and len(current_chunk) >= 2
                
                if cond_word_count or cond_punctuation or cond_time_gap or cond_duration or cond_wpm:
                    dynamic_word_chunks.append(current_chunk)
                    current_chunk = [w]
                else:
                    current_chunk.append(w)
                    
        if current_chunk:
            dynamic_word_chunks.append(current_chunk)

        # Resolve Auto Subtitle Style
        if subtitle_style == "auto":
            total_words = len(words_list)
            total_duration = end_time - start_time
            overall_wpm = (total_words / total_duration * 60) if total_duration > 0 else 0
            
            if overall_wpm > 200:
                resolved_style = "karaoke"
            elif overall_wpm < 130:
                resolved_style = "classic"
            else:
                resolved_style = "kinetic"

        # Format & Render Events
        highlight_count_total = 0
        emphasis_count_total = 0
        number_count_total = 0
        question_count_total = 0
        words_per_chunk_sum = 0
        chunk_durations_sum = 0
        
        EMPHASIS_WORDS = {
            "money", "million", "billion", "ai", "startup", "success", 
            "secret", "mistake", "never", "always", "truth", "future", "business"
        }
        QUESTION_WORDS = {"why", "how", "what", "who", "where", "when", "which", "whose", "whom"}
        
        is_first_event = True
        raw_events = []
        
        # Precompute chunk timings to prevent overlaps
        chunk_timings = []
        last_end = 0.0
        for chunk_idx, chunk_words in enumerate(dynamic_word_chunks):
            spoken_start = chunk_words[0]["start"] - start_time
            spoken_end = chunk_words[-1]["end"] - start_time
            
            # Apply punctuation pause (+250ms)
            last_word_text = chunk_words[-1]["text"].strip()
            punc_pause = 0.25 if (last_word_text and last_word_text[-1] in SENTENCE_ENDINGS) else 0.0
            
            c_start = max(last_end, spoken_start - 0.1)
            c_end = spoken_end + punc_pause
            
            if chunk_idx + 1 < len(dynamic_word_chunks):
                next_spoken_start = dynamic_word_chunks[chunk_idx + 1][0]["start"] - start_time
                c_end = min(c_end, max(spoken_end, next_spoken_start - 0.1))
            else:
                c_end = min(c_end, end_time - start_time)
                
            if c_end - c_start < 0.3:
                if chunk_idx + 1 < len(dynamic_word_chunks):
                    next_spoken_start = dynamic_word_chunks[chunk_idx + 1][0]["start"] - start_time
                    c_end = min(c_start + 0.3, next_spoken_start)
                else:
                    c_end = c_start + 0.3
                    
            if c_start >= c_end:
                c_end = c_start + 0.05
                
            last_end = c_end
            chunk_timings.append((c_start, c_end))

        for chunk_idx, chunk_words in enumerate(dynamic_word_chunks):
            words_per_chunk_sum += len(chunk_words)
            c_start, c_end = chunk_timings[chunk_idx]
            chunk_durations_sum += (c_end - c_start)
            
            split_idx = -1
            n_words = len(chunk_words)
            total_len = sum(len(w["text"]) for w in chunk_words) + n_words - 1
            
            if n_words >= 2:
                ATOMIC_PAIRS = {
                    ("sam", "altman"), ("new", "york"), ("artificial", "intelligence"), 
                    ("opena", "i"), ("open", "ai"), ("$10", "million"), ("10", "million")
                }
                best_score = -99999
                for i in range(n_words - 1):
                    w_curr = re.sub(r'[^\w$]', '', chunk_words[i]["text"]).lower()
                    w_next = re.sub(r'[^\w$]', '', chunk_words[i+1]["text"]).lower()
                    if (w_curr, w_next) in ATOMIC_PAIRS:
                        continue
                    line1_len = sum(len(chunk_words[k]["text"]) + 1 for k in range(i + 1)) - 1
                    line2_len = sum(len(chunk_words[k]["text"]) + 1 for k in range(i + 1, n_words)) - 1
                    
                    score = 0
                    prev_text = chunk_words[i]["text"].strip()
                    if prev_text and prev_text[-1] in {'.', ',', '?', '!', ';', ':'}:
                        score += 100
                    score -= abs(line1_len - line2_len) * 2
                    if (n_words - i - 1) == 1:
                        score -= 50
                    if line1_len > 22:
                        score -= (line1_len - 22) * 5
                    if line2_len > 22:
                        score -= (line2_len - 22) * 5
                        
                    if score > best_score:
                        best_score = score
                        split_idx = i
                        
                if total_len <= 18 and n_words <= 2:
                    split_idx = -1

            if resolved_style == "classic":
                styled_words = []
                for j, w in enumerate(chunk_words):
                    w_text = w["text"].upper()
                    if j == 0:
                        styled_words.append(f"{{\\c{highlight_color_ass}}}{w_text}{{\\c{primary_color_ass}}}")
                    else:
                        styled_words.append(w_text)
                    if j == split_idx:
                        styled_words.append("\\N")
                
                styled_text = " ".join(styled_words).replace(" \\N ", "\\N").replace("\\N ", "\\N").replace(" \\N", "\\N")
                start_str = format_ass_time(c_start)
                end_str = format_ass_time(c_end)
                raw_events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{styled_text}")
                is_first_event = False
                continue
                
            for active_idx in range(len(chunk_words)):
                if active_idx == 0:
                    evt_start = c_start
                else:
                    evt_start = max(c_start, chunk_words[active_idx]["start"] - start_time)
                    
                if active_idx == len(chunk_words) - 1:
                    evt_end = c_end
                else:
                    evt_end = min(c_end, chunk_words[active_idx + 1]["start"] - start_time)
                    
                if evt_end <= evt_start:
                    evt_end = evt_start + 0.05
                    
                parts = []
                for j, w in enumerate(chunk_words):
                    w_text = w["text"].upper()
                    if j == active_idx:
                        clean_word = re.sub(r'[^\w$]', '', w["text"]).lower()
                        color = highlight_color_ass
                        
                        if clean_word in EMPHASIS_WORDS:
                            color = "&H001A9FFF&" # Orange
                            emphasis_count_total += 1
                        elif any(c in w["text"] for c in "0123456789$"):
                            color = "&H0073D52E&" # Green
                            number_count_total += 1
                        elif "?" in w["text"] or clean_word in QUESTION_WORDS:
                            color = "&H00E9EC10&" # Cyan
                            question_count_total += 1
                        else:
                            highlight_count_total += 1
                            
                        scale_active = int(100 * pop_scale)
                        scale_mid = int(100 * (1.0 + (pop_scale - 1.0) * 0.44))
                        anim_tag = f"\\fscx100\\fscy100\\1a&H26&\\t(0,80,\\fscx{scale_active}\\fscy{scale_active}\\1a&H00&)\\t(80,180,\\fscx{scale_mid}\\fscy{scale_mid})\\t(180,{pop_duration},\\fscx100\\fscy100)"
                        
                        first_event_fade = "\\fad(120,0)" if is_first_event else ""
                        
                        parts.append(f"{{{first_event_fade}{anim_tag}\\c{color}}}{w_text}{{\\fscx100\\fscy100\\c{primary_color_ass}}}")
                    else:
                        if resolved_style == "karaoke" and j < active_idx:
                            clean_word = re.sub(r'[^\w$]', '', w["text"]).lower()
                            color = highlight_color_ass
                            if clean_word in EMPHASIS_WORDS:
                                color = "&H001A9FFF&"
                            elif any(c in w["text"] for c in "0123456789$"):
                                color = "&H0073D52E&"
                            elif "?" in w["text"] or clean_word in QUESTION_WORDS:
                                color = "&H00E9EC10&"
                            parts.append(f"{{\\c{color}}}{w_text}{{\\c{primary_color_ass}}}")
                        else:
                            parts.append(w_text)
                            
                    if j == split_idx:
                        parts.append("\\N")
                        
                styled_text = " ".join(parts).replace(" \\N ", "\\N").replace("\\N ", "\\N").replace(" \\N", "\\N")
                start_str = format_ass_time(evt_start)
                end_str = format_ass_time(evt_end)
                raw_events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{styled_text}")
                is_first_event = False

        # Performance Guardrail: max 600 events per minute
        duration_of_clip = end_time - start_time
        event_density = len(raw_events) / (duration_of_clip / 60.0) if duration_of_clip > 0 else 0
        
        if event_density > 600:
            logger.warning(f"Subtitle event density too high ({event_density:.1f} events/min > 600). Regressing to Classic mode for render stability.")
            fallback_used = True
            resolved_style = "classic"
            classic_events = []
            is_first_event = True
            for chunk_idx, chunk_words in enumerate(dynamic_word_chunks):
                c_start, c_end = chunk_timings[chunk_idx]
                
                split_idx = -1
                n_words = len(chunk_words)
                total_len = sum(len(w["text"]) for w in chunk_words) + n_words - 1
                
                if n_words >= 2:
                    ATOMIC_PAIRS = {
                        ("sam", "altman"), ("new", "york"), ("artificial", "intelligence"), 
                        ("opena", "i"), ("open", "ai"), ("$10", "million"), ("10", "million")
                    }
                    best_score = -99999
                    for i in range(n_words - 1):
                        w_curr = re.sub(r'[^\w$]', '', chunk_words[i]["text"]).lower()
                        w_next = re.sub(r'[^\w$]', '', chunk_words[i+1]["text"]).lower()
                        if (w_curr, w_next) in ATOMIC_PAIRS:
                            continue
                        line1_len = sum(len(chunk_words[k]["text"]) + 1 for k in range(i + 1)) - 1
                        line2_len = sum(len(chunk_words[k]["text"]) + 1 for k in range(i + 1, n_words)) - 1
                        
                        score = 0
                        prev_text = chunk_words[i]["text"].strip()
                        if prev_text and prev_text[-1] in {'.', ',', '?', '!', ';', ':'}:
                            score += 100
                        score -= abs(line1_len - line2_len) * 2
                        if (n_words - i - 1) == 1:
                            score -= 50
                        if line1_len > 22:
                            score -= (line1_len - 22) * 5
                        if line2_len > 22:
                            score -= (line2_len - 22) * 5
                            
                        if score > best_score:
                            best_score = score
                            split_idx = i
                            
                    if total_len <= 18 and n_words <= 2:
                        split_idx = -1
                
                styled_words = []
                for j, w in enumerate(chunk_words):
                    w_text = w["text"].upper()
                    if j == 0:
                        styled_words.append(f"{{\\c{highlight_color_ass}}}{w_text}{{\\c{primary_color_ass}}}")
                    else:
                        styled_words.append(w_text)
                    if j == split_idx:
                        styled_words.append("\\N")
                
                styled_text = " ".join(styled_words).replace(" \\N ", "\\N").replace("\\N ", "\\N").replace(" \\N", "\\N")
                start_str = format_ass_time(c_start)
                end_str = format_ass_time(c_end)
                classic_events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{styled_text}")
            events += classic_events
        else:
            events += raw_events

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(header + "\n" + "\n".join(events))
            
    except Exception as exc:
        logger.warning(f"Error during subtitle generation: {exc}. Performing Safe Mode fallback to Classic style.")
        fallback_used = True
        resolved_style = "classic"
        try:
            # Safe fallback setup: Arial font, standard white text, yellow highlight, 450 margin
            primary_color_ass = "&H00FFFFFF&"
            highlight_color_ass = "&H0000D4FF&"
            outline_color_ass = "&H00000000&"
            back_color_ass = "&H8C000000&"
            
            header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},{primary_color_ass},&H0000FFFF&,{outline_color_ass},{back_color_ass},-1,0,0,0,100,100,0,0,1,{outline_thickness},{shadow_depth},2,10,10,450,1
"""
            events = [
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
            ]
            
            # Simple grouping by 3 words for fallback simplicity
            fallback_chunks = []
            chunk = []
            for w in words_list:
                chunk.append(w)
                if len(chunk) >= 3 or (w["text"].strip() and w["text"].strip()[-1] in {'.', ',', '?', '!'}):
                    fallback_chunks.append(chunk)
                    chunk = []
            if chunk:
                fallback_chunks.append(chunk)
                
            # Precompute fallback timings to prevent overlap
            fallback_timings = []
            last_end = 0.0
            for chunk_idx, chunk_words in enumerate(fallback_chunks):
                spoken_start = chunk_words[0]["start"] - start_time
                spoken_end = chunk_words[-1]["end"] - start_time
                c_start = max(last_end, spoken_start - 0.1)
                c_end = spoken_end
                
                if chunk_idx + 1 < len(fallback_chunks):
                    next_spoken_start = fallback_chunks[chunk_idx + 1][0]["start"] - start_time
                    c_end = min(c_end, max(spoken_end, next_spoken_start - 0.1))
                else:
                    c_end = min(c_end, end_time - start_time)
                    
                if c_end - c_start < 0.3:
                    if chunk_idx + 1 < len(fallback_chunks):
                        next_spoken_start = fallback_chunks[chunk_idx + 1][0]["start"] - start_time
                        c_end = min(c_start + 0.3, next_spoken_start)
                    else:
                        c_end = c_start + 0.3
                        
                if c_start >= c_end:
                    c_end = c_start + 0.05
                    
                last_end = c_end
                fallback_timings.append((c_start, c_end))
                
            for chunk_idx, chunk_words in enumerate(fallback_chunks):
                c_start, c_end = fallback_timings[chunk_idx]
                
                styled_words = []
                for j, w in enumerate(chunk_words):
                    w_text = w["text"].upper()
                    if j == 0:
                        styled_words.append(f"{{\\c{highlight_color_ass}}}{w_text}{{\\c{primary_color_ass}}}")
                    else:
                        styled_words.append(w_text)
                
                styled_text = " ".join(styled_words)
                start_str = format_ass_time(c_start)
                end_str = format_ass_time(c_end)
                events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{styled_text}")
                
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(header + "\n" + "\n".join(events))
                
            highlight_count_total = len(words_list) // 3
            emphasis_count_total = 0
            dynamic_word_chunks = fallback_chunks
            words_per_chunk_sum = len(words_list)
            
        except Exception as fallback_exc:
            logger.error(f"Fallback subtitle generation completely failed: {fallback_exc}. Writing empty ASS file.")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write("")
            return {
                "ass_event_count": 0,
                "fallback_used": True,
                "highlight_count": 0,
                "emphasis_count": 0,
                "words_per_chunk": 0.0,
                "reading_speed": 0.0,
                "subtitle_style": "classic"
            }

    # Final metrics reporting
    num_events = max(0, len(events) - 2)
    avg_words = 0.0
    if len(dynamic_word_chunks) > 0:
        avg_words = words_per_chunk_sum / len(dynamic_word_chunks)
        
    total_words = len(words_list)
    total_duration = end_time - start_time
    avg_wpm = (total_words / total_duration * 60) if total_duration > 0 else 0
    
    return {
        "ass_event_count": num_events,
        "fallback_used": fallback_used,
        "highlight_count": highlight_count_total,
        "emphasis_count": emphasis_count_total,
        "words_per_chunk": round(avg_words, 2),
        "reading_speed": round(avg_wpm, 2),
        "subtitle_style": resolved_style
    }


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
    virality_score: float = 0.0
    detailed_scores: Dict[str, float] = {}
    experiment_id: Optional[str] = ""
    variant_id: Optional[str] = ""
    scoring_version: Optional[str] = ""
    prompt_version: Optional[str] = ""
    weight_version: Optional[str] = ""
    encoder_used: Optional[str] = ""
    boundary_quality: Optional[Dict] = None
    camera_qa: Optional[Dict] = None
    subtitle_zone_detected: bool = False
    subtitle_zone_height: int = 0
    upload_package: Optional[Dict] = None
    # Phase 24: AI Emotion-Matched Background Music
    emotion: Optional[str] = None
    energy_level: Optional[int] = None
    music_description: Optional[str] = None
    volume_pct: Optional[int] = None
    music_source: Optional[str] = None  # "elevenlabs", "freesound", or "none"
    has_music: bool = False
    music_category: Optional[str] = None
    music_file: Optional[str] = None
    license: Optional[str] = None
    license_id: Optional[str] = None
    # Phase 25: Cinematic Music Layering
    audio_layers: List[str] = []
    impact_moments: int = 0
    impact_moments_detail: Optional[List[Dict]] = None
    # Phase 26: Like Prompt Overlay
    like_overlay_added: bool = False


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

# Concurrency Semaphore: restricts CPU-heavy video downloads and OpenCV clipping to 3 active tasks
# Initialized dynamically in the running event loop to prevent RuntimeError
SEMAPHORE = None

async def run_pipeline(
    job_id: str, 
    url: str, 
    api_key: str, 
    num_clips: Optional[int] = None,
    subtitle_style: str = "kinetic",
    font_name: str = "Anton",
    font_size: int = 75,
    pop_scale: float = 1.18,
    pop_duration: int = 260,
    primary_color: str = "#FFFFFF",
    highlight_color: str = "#FFD400",
    outline_color: str = "#000000",
    outline_thickness: int = 4,
    shadow_depth: int = 2,
    creator_preset: str = "custom",
    debug_camera_tracking: bool = False,
    force_refresh: bool = False,
    bypass_camera_qa: bool = False
):
    """Executes the full video analysis and clipping pipeline."""
    global SEMAPHORE
    if SEMAPHORE is None:
        SEMAPHORE = asyncio.Semaphore(3)

    job = jobs[job_id]
    download_dir = os.path.join("output", job_id)
    os.makedirs(download_dir, exist_ok=True)
    
    # Set status to pending while waiting in the concurrency semaphore queue
    job.status = "pending"
    job.progress = 5
    job.message = "Waiting in queue for active slot..."
    
    # Initialize duration tracking variables to prevent UnboundLocalError under check-skips/failures
    duration_step1 = 0.0
    duration_step2 = 0.0
    duration_step3 = 0.0
    duration_step4 = 0.0

    async with SEMAPHORE:
        video_path = None
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
            
            # Fix C: Early YouTube Availability Check
            is_avail, avail_error = await loop.run_in_executor(None, check_youtube_availability, video_id)
            if not is_avail:
                job.status = "unavailable"
                job.progress = 100
                job.message = f"Video is unavailable: {avail_error}"
                job.error = avail_error
                logger.info(f"Video {video_id} is unavailable: {avail_error}. Aborting pipeline.")
                return

            def on_state_change(status, message):
                def update():
                    job.status = status
                    job.progress = 20
                    job.message = message
                loop.call_soon_threadsafe(update)
                
            transcript_meta = {}
            t_start_step1 = time.perf_counter()
            raw_transcript = await loop.run_in_executor(
                None, 
                fetch_transcript_list, 
                video_id, 
                transcript_meta, 
                on_state_change
            )
            duration_step1 = time.perf_counter() - t_start_step1
            
            # Support 10-minute representative segments for specific long-form podcasts (Category D)
            REPRESENTATIVE_SEGMENT_IDS = {"DcWqzZ3I2cY", "Ff4fRgnuFgQ", "eTBAxD6lt2g"}
            download_range = None
            if video_id in REPRESENTATIVE_SEGMENT_IDS:
                download_range = (0.0, 600.0)
                # Filter raw_transcript to only include items starting within the 10-minute limit (600s)
                raw_transcript = [entry for entry in raw_transcript if entry.start < 600.0]
                logger.info(f"Video {video_id} is in representative segment list. Restricting transcript to first 10 minutes.")

            # Save transcript metrics to the database
            try:
                from analytics_repository import db as analytics_db
                analytics_db.save_transcript_metric(
                    video_id=video_id,
                    source=transcript_meta.get("source", "unknown"),
                    failures=transcript_meta.get("failures", []),
                    fallback_used=bool(transcript_meta.get("fallback_used", False)),
                    duration=float(transcript_meta.get("duration", 0.0))
                )
                logger.info(f"Saved transcript metrics for video {video_id} to database.")
            except Exception as db_err:
                logger.warning(f"Failed to save transcript metrics to database: {db_err}")
            
            # Format transcript text with precise index and float timestamps for Gemini
            formatted_lines = []
            for idx, entry in enumerate(raw_transcript):
                start = entry.start
                end = entry.start + entry.duration
                timestamp = f"[{start:.2f} - {end:.2f}]"
                text = entry.text.replace('\n', ' ')
                formatted_lines.append(f"[{idx}] {timestamp} {text}")
            transcript_text = "\n".join(formatted_lines)
            
            # Generate deterministic checkpoint key (Phase 29 updated requirements)
            import hashlib
            import json
            settings_dict = {
                "pipeline_version": "1.0.0",
                "prompt_version": "prompt_v1",
                "num_clips": num_clips,
                "bypass_camera_qa": bypass_camera_qa,
                "music_enabled": bool(os.getenv("ELEVENLABS_API_KEY", "").strip() or os.getenv("FREESOUND_API_KEY", "").strip()),
                "subtitle_style": subtitle_style,
                "font_name": font_name,
                "font_size": font_size,
                "pop_scale": pop_scale,
                "pop_duration": pop_duration,
                "primary_color": primary_color,
                "highlight_color": highlight_color,
                "outline_color": outline_color,
                "outline_thickness": outline_thickness,
                "shadow_depth": shadow_depth,
                "creator_preset": creator_preset,
                "language": "en"  # default language
            }
            serialized_settings = json.dumps(settings_dict, sort_keys=True)
            settings_hash = hashlib.sha256(serialized_settings.encode("utf-8")).hexdigest()[:16]
            checkpoint_key = f"{video_id}_{settings_hash}"
            logger.info(f"[Checkpoint] Generated deterministic key {checkpoint_key} for video {video_id}")

            # Check cache in DB if force_refresh is False
            cached_clips = []
            if not force_refresh:
                try:
                    from analytics_repository import db as analytics_db
                    cached_clips = analytics_db.get_clips_by_video_id(video_id)
                    if cached_clips:
                        logger.info(f"[Cache HIT] Found {len(cached_clips)} completed clips for video {video_id} in database. Skipping Scout + Curator + Virality Scoring.")
                except Exception as cache_err:
                    logger.warning(f"Error checking cached clips in database: {cache_err}")

            if cached_clips:
                clips_data = cached_clips
                # Populate pipeline_meta to keep stats and reports happy
                pipeline_meta = {
                    "scout_count": len(cached_clips),
                    "curator_count": len(cached_clips),
                    "dedup_count": len(cached_clips),
                    "skip_reasons": ["Loaded from database cache (Cache HIT)"]
                }
            else:
                # Step 2: Analyze with Gemini
                job.status = "analyzing"
                job.progress = 30
                job.message = "Analyzing transcript with Gemini AI to identify interesting moments..."
                
                pipeline_meta = {}
                t_start_step2 = time.perf_counter()
                from functools import partial
                analyze_func = partial(
                    analyze_with_gemini,
                    transcript_text,
                    raw_transcript,
                    api_key,
                    num_clips,
                    0.4,
                    pipeline_meta,
                    video_id=video_id,
                    force_refresh=force_refresh,
                    checkpoint_key=checkpoint_key
                )
                clips_data = await loop.run_in_executor(None, analyze_func)
                duration_step2 = time.perf_counter() - t_start_step2

            scout_count = pipeline_meta.get("scout_count", 0)
            curator_count = pipeline_meta.get("curator_count", 0)
            dedup_count = pipeline_meta.get("dedup_count", 0)
            skip_reasons = pipeline_meta.get("skip_reasons", [])
            
            avg_virality = 0.0
            if clips_data:
                avg_virality = sum(float(c.get("virality_score", 0.0)) for c in clips_data) / len(clips_data)
            
            # Print Structured Clip Generation Report
            logger.info("=" * 60)
            logger.info("CLIP GENERATION REPORT:")
            logger.info(f"  Requested:   {num_clips if num_clips is not None else 'Dynamic'}")
            logger.info(f"  Scout found: {scout_count} candidates")
            logger.info(f"  Curator sel: {curator_count}")
            logger.info(f"  After dedup: {dedup_count}")
            logger.info(f"  Exported:    {len(clips_data) if clips_data else 0}")
            logger.info(f"  Average post-curation virality: {avg_virality:.2f}/10")
            logger.info(f"  Skipped:     {len(skip_reasons)} clips")
            for r in skip_reasons:
                logger.info(f"    - {r}")
            logger.info("=" * 60)
            
            # Write clip_generation_report.md
            artifact_dir = r"C:\Users\anils\.gemini\antigravity\brain\1b3acd38-6039-400c-975c-a12268af0711"
            if os.path.exists(artifact_dir):
                report_path = os.path.join(artifact_dir, "clip_generation_report.md")
                skip_reasons_md = "\n".join(f"- {r}" for r in skip_reasons) if skip_reasons else "*None*"
                
                clips_details_md = ""
                if clips_data:
                    for idx, c in enumerate(clips_data):
                        clips_details_md += f"""### {idx+1}. {c.get('title')}
- **Time Range**: {c.get('start_time')}s - {c.get('end_time')}s (duration: {c.get('end_time') - c.get('start_time'):.2f}s)
- **Virality Score**: {c.get('virality_score', 0.0)}/10
- **Scoring Reasoning**: {c.get('virality_reasoning', 'N/A')}
- **Shorts Title**: `{c.get('shorts_title')}`
- **Description**: {c.get('shorts_description')}

"""
                else:
                    clips_details_md = "*No clips passed the strict quality bar.*"
                
                report_content = f"""# Clip Generation Report

This report summarizes the clip filtering pipeline stages and details how many clips were scouted, curated, and validated with their post-curation virality scores.

## Summary Metrics

- **Requested Clips**: {num_clips if num_clips is not None else 'Dynamic'}
- **Scout Found Candidates**: {scout_count}
- **Curator Selected (Passed Quality Bar)**: {curator_count}
- **After Deduplication/Validation**: {dedup_count}
- **Final Exported Clips**: {len(clips_data) if clips_data else 0}
- **Average Approved Virality Score**: {avg_virality:.2f}/10

## Approved Clips (Sorted by Virality Score)

{clips_details_md}

## Discarded / Skipped Clips Details

{skip_reasons_md}
"""
                try:
                    with open(report_path, "w", encoding="utf-8") as f:
                        f.write(report_content)
                except Exception as write_err:
                    logger.warning(f"Could not write clip_generation_report.md artifact: {write_err}")
            
            if not clips_data:
                job.clips = []
                job.status = "completed"
                job.progress = 100
                job.message = "No spoken dialogue detected"
                logger.info(f"No spoken dialogue/clips detected for video {video_id}. Job completed gracefully with 0 clips.")
                return
                
            # Step 3: Download Video
            job.status = "downloading"
            job.progress = 50
            job.message = "Downloading video from YouTube..."
            
            def on_download_progress(pct):
                def update():
                    job.progress = 50 + int(pct * 0.2)  # maps 0-100 download percent to 50-70 job progress
                    job.message = f"Downloading video from YouTube... {pct}%"
                loop.call_soon_threadsafe(update)
                
            t_start_step3 = time.perf_counter()
            video_path = await loop.run_in_executor(None, download_video, url, download_dir, on_download_progress, video_id, None, download_range)
            duration_step3 = time.perf_counter() - t_start_step3
            # Step 4: Extract clips
            job.status = "clipping"
            job.progress = 75
            job.message = "Extracting clips with ffmpeg..."
            
            clips = []
            clip_timings = []
            rejected_by_camera_qa = []
            t_start_step4 = time.perf_counter()
            for i, clip_data in enumerate(clips_data):
                # 1. Generate deterministic clip_id based on video_id, title, start/end time
                import hashlib
                clip_key_str = f"{video_id}_{clip_data['title']}_{clip_data['start_time']:.2f}_{clip_data['end_time']:.2f}"
                clip_id = hashlib.sha256(clip_key_str.encode("utf-8")).hexdigest()[:8]

                clips_output_dir = os.path.join("output", "clips")
                os.makedirs(clips_output_dir, exist_ok=True)
                clip_metadata_path = os.path.join(clips_output_dir, f"{clip_id}_metadata.json")

                # Check for cached clip metadata to skip reprocessing
                if not force_refresh and os.path.exists(clip_metadata_path):
                    try:
                        with open(clip_metadata_path, "r", encoding="utf-8") as mf:
                            cached_data = json.load(mf)
                        
                        # Verify the referenced output video file actually exists
                        cached_filename = cached_data.get("filename", "")
                        cached_video_path = os.path.join(clips_output_dir if "with_music" in cached_filename else download_dir, cached_filename)
                        
                        if os.path.exists(cached_video_path) and os.path.getsize(cached_video_path) > 10240:
                            logger.info(f"[Checkpoint] Resuming clip {clip_id} from cache: {cached_video_path}")
                            clip_info = ClipInfo(**cached_data)
                            clips.append(clip_info)
                            continue
                    except Exception as cached_err:
                        logger.warning(f"Failed to load cached clip metadata for {clip_id}: {cached_err}. Reprocessing.")

                # Wrap each clip processing in try/except to isolate failures
                try:
                    job.message = f"Extracting clip {i+1} of {len(clips_data)}: {clip_data['title']}"
                    job.progress = 75 + int((i / len(clips_data)) * 20)
                    
                    output_filename = f"clip_{clip_id}.mp4"
                    output_path = os.path.join(download_dir, output_filename)
                    
                    # Before extraction, refine end boundary using audio
                    try:
                        from clipper import detect_silence_boundaries
                        adjusted_end = detect_silence_boundaries(
                            video_path, clip_data['start_time'], clip_data['end_time']
                        )
                        if adjusted_end != clip_data['end_time']:
                            logger.info(f"Audio boundary refinement: {clip_data['end_time']:.2f} → {adjusted_end:.2f}")
                            clip_data['end_time'] = adjusted_end
                            
                            if "boundary_quality" in clip_data:
                                clip_data["boundary_quality"]["audio_refined"] = True
                                from analyzer import calculate_completeness_score
                                clip_data["boundary_quality"]["story_completeness_score"] = calculate_completeness_score(
                                    clip_data, raw_transcript, audio_refined=True
                                )
                    except Exception as silence_err:
                        logger.warning(f"Failed to perform audio silence boundary refinement: {silence_err}")
                    
                    # Fallback setup for boundary_quality if missing
                    if "boundary_quality" not in clip_data:
                        from analyzer import calculate_completeness_score
                        try:
                            start_idx = clip_data.get("start_index", 0)
                            end_idx = clip_data.get("end_index", 0)
                            start_text = raw_transcript[start_idx].text.strip() if start_idx < len(raw_transcript) else ""
                            from analyzer import CONJUNCTION_STARTS, FILLER_STARTS, SENTENCE_ENDINGS
                            first_word = ""
                            if start_text:
                                match = re.match(r'^\w+', start_text)
                                if match:
                                    first_word = match.group(0).lower()
                            start_clean = first_word not in CONJUNCTION_STARTS and first_word not in FILLER_STARTS
                            
                            end_text = raw_transcript[end_idx].text.strip() if end_idx < len(raw_transcript) else ""
                            end_clean = bool(end_text and end_text[-1] in SENTENCE_ENDINGS)
                            
                            initial_score = calculate_completeness_score(clip_data, raw_transcript, audio_refined=False)
                            clip_data["boundary_quality"] = {
                                "start_clean": start_clean,
                                "end_clean": end_clean,
                                "audio_refined": False,
                                "story_completeness_score": initial_score
                            }
                        except Exception as meta_err:
                            logger.warning(f"Could not compute initial boundary_quality: {meta_err}")
                            clip_data["boundary_quality"] = {
                                "start_clean": True,
                                "end_clean": True,
                                "audio_refined": False,
                                "story_completeness_score": 9.0
                            }

                    # Generate ASS subtitle file
                    ass_path = os.path.join(download_dir, f"sub_{clip_id}.ass")
                    
                    # Wrap ASS generation in try-except for Safe Mode fallback
                    fallback_used = False
                    ass_metrics = {}
                    try:
                        ass_metrics = generate_ass(
                            raw_transcript,
                            clip_data['start_time'],
                            clip_data['end_time'],
                            ass_path,
                            subtitle_style=subtitle_style,
                            font_name=font_name,
                            font_size=font_size,
                            pop_scale=pop_scale,
                            pop_duration=pop_duration,
                            primary_color=primary_color,
                            highlight_color=highlight_color,
                            outline_color=outline_color,
                            outline_thickness=outline_thickness,
                            shadow_depth=shadow_depth
                        )
                        fallback_used = ass_metrics.get("fallback_used", False)
                    except Exception as ass_err:
                        logger.warning(f"Failed to generate custom ASS subtitles: {ass_err}. Falling back to classic.")
                        fallback_used = True
                        try:
                            ass_metrics = generate_ass(
                                raw_transcript,
                                clip_data['start_time'],
                                clip_data['end_time'],
                                ass_path,
                                subtitle_style="classic",
                                font_name="Arial",
                                font_size=font_size,
                                pop_scale=1.0,
                                pop_duration=0,
                                primary_color="#FFFFFF",
                                highlight_color="#FFD400",
                                outline_color="#000000",
                                outline_thickness=4,
                                shadow_depth=2
                            )
                        except Exception as fallback_err:
                            logger.error(f"Fallback subtitle generation also failed: {fallback_err}. Writing empty ASS file.")
                            with open(ass_path, "w", encoding="utf-8") as f:
                                f.write("")
                            ass_metrics = {
                                "ass_event_count": 0,
                                "fallback_used": True,
                                "highlight_count": 0,
                                "emphasis_count": 0,
                                "words_per_chunk": 0.0,
                                "reading_speed": 0.0,
                                "subtitle_style": "classic"
                            }

                    from subtitle_detector import detect_subtitle_zone, has_subtitles
                    subs_detected = has_subtitles(video_path)
                    subs_height = detect_subtitle_zone(video_path) if subs_detected else 0
                    metadata_dict = {
                        "debug_camera_tracking": debug_camera_tracking,
                        "subtitle_zone_height": subs_height,
                        "subtitle_zone_detected": subs_detected,
                        "bypass_camera_qa": bypass_camera_qa
                    }
                    t_clip_start = time.perf_counter()
                    _, encoder_used = await loop.run_in_executor(
                        None, 
                        extract_clip, 
                        video_path, 
                        clip_data['start_time'], 
                        clip_data['end_time'], 
                        output_path,
                        ass_path,
                        metadata_dict
                    )
                    clip_dur = time.perf_counter() - t_clip_start
                    render_time_ms = int(clip_dur * 1000)
                    clip_timings.append((clip_data['title'], clip_dur))
                    
                    duration = clip_data['end_time'] - clip_data['start_time']
                    
                    # Fetch resolved values
                    resolved_style = ass_metrics.get("subtitle_style", subtitle_style)
                    words_per_chunk = ass_metrics.get("words_per_chunk", 0.0)
                    reading_speed = ass_metrics.get("reading_speed", 0.0)
                    highlight_count = ass_metrics.get("highlight_count", 0)
                    ass_event_count = ass_metrics.get("ass_event_count", 0)
                    face_position = metadata_dict.get("face_position", "MID")
                    
                    camera_qa_data = metadata_dict.get('camera_qa')
                    qa_passed = True
                    if camera_qa_data:
                        qa_passed = camera_qa_data.get('qa_passed', True)
                    
                    if not qa_passed:
                        logger.warning(f"Clip '{clip_data['title']}' failed Camera QA. Excluding from final exports.")
                        rejected_by_camera_qa.append((clip_data, camera_qa_data))
                        # Remove output files to save space
                        if os.path.exists(output_path):
                            try:
                                os.remove(output_path)
                            except Exception as delete_err:
                                logger.warning(f"Could not remove QA-failed output video: {delete_err}")
                        if os.path.exists(ass_path):
                            try:
                                os.remove(ass_path)
                            except Exception as delete_err:
                                logger.warning(f"Could not remove QA-failed subtitle file: {delete_err}")
                    else:
                        # Generate YouTube Upload Package (Phase 22)
                        package = None
                        package_json_path = os.path.join(clips_output_dir, f"{clip_id}_upload_package.json")
                        
                        # Cache check for upload package
                        if not force_refresh and os.path.exists(package_json_path):
                            try:
                                with open(package_json_path, "r", encoding="utf-8") as jf:
                                    package = json.load(jf)
                                logger.info(f"Reusing existing cached upload package for clip {clip_id}.")
                            except Exception as pkg_cache_err:
                                logger.warning(f"Failed to load cached upload package for {clip_id}: {pkg_cache_err}")

                        if not package:
                            try:
                                from upload_package import generate_upload_package
                                # Construct clip text
                                start_idx = clip_data.get('start_index', 0)
                                end_idx = clip_data.get('end_index', 0)
                                clip_lines = []
                                for line_idx in range(start_idx, min(end_idx + 1, len(raw_transcript))):
                                    clip_lines.append(raw_transcript[line_idx].text)
                                clip_text = " ".join(clip_lines)
                                
                                hook_line = raw_transcript[start_idx].text if start_idx < len(raw_transcript) else ""
                                
                                package = generate_upload_package(
                                    clip_text=clip_text,
                                    hook=hook_line,
                                    virality_score=clip_data.get('virality_score', 0.0),
                                    virality_reasoning=clip_data.get('reason', 'Interesting peak point.'),
                                    duration=duration,
                                    api_key=api_key
                                )
                                
                                if package:
                                    # Save to files
                                    package_txt_path = os.path.join(clips_output_dir, f"{clip_id}_upload_package.txt")
                                    
                                    titles = package.get("titles", ["Title 1", "Title 2", "Title 3"])
                                    desc = package.get("description", "")
                                    tags = " ".join(package.get("hashtags", []))
                                    thumb = package.get("thumbnail_text", "")
                                    post_time = package.get("best_time_to_post", "")
                                    audience = package.get("target_audience", "")
                                    hook_anal = package.get("hook_analysis", "")
                                    keywords = ", ".join(package.get("keywords", []))
                                    category = package.get("category", "")
                                    language = package.get("language", "")
                                    intent = package.get("search_intent", "")
                                    
                                    package_txt_content = f"""=== YOUTUBE UPLOAD PACKAGE ===
Clip: {clip_data['title']}
Duration: {duration:.1f}s | Virality: {clip_data.get('virality_score', 0.0)}/10

TITLE OPTIONS (ranked):
1. {titles[0] if len(titles) > 0 else ""} &larr; RECOMMENDED
2. {titles[1] if len(titles) > 1 else ""}
3. {titles[2] if len(titles) > 2 else ""}

DESCRIPTION:
{desc}

HASHTAGS:
{tags}

KEYWORDS:
{keywords}

THUMBNAIL TEXT: {thumb}

BEST TIME TO POST: {post_time}

TARGET AUDIENCE: {audience}

HOOK ANALYSIS: {hook_anal}

CATEGORY: {category}
LANGUAGE: {language}
SEARCH INTENT: {intent}"""

                                    with open(package_txt_path, "w", encoding="utf-8") as pf:
                                        pf.write(package_txt_content)
                                    logger.info(f"Saved YouTube upload package to {package_txt_path}")
                                    
                                    with open(package_json_path, "w", encoding="utf-8") as jf:
                                        json.dump(package, jf, indent=2)
                                    logger.info(f"Saved YouTube upload package JSON to {package_json_path}")
                            except Exception as pkg_err:
                                logger.error(f"Failed to generate/save YouTube upload package for {clip_id}: {pkg_err}")
                                package = None

                        # -------------------------------------------------------
                        # Phase 24 — AI Emotion-Matched Background Music
                        # -------------------------------------------------------
                        emotion_data = None
                        music_source = "none"
                        final_filename = output_filename
                        with_music_result = output_path
                        audio_layers_p25 = []
                        impact_count_p25 = 0
                        impact_detail_p25 = []
                        music_category_p25 = None
                        music_file_p25 = None
                        license_p25 = None
                        license_id_p25 = None

                        try:
                            from music_selector import analyze_clip_emotion, fetch_elevenlabs_music, mix_music_into_clip

                            # Reuse clip_text / hook_line built during upload package step
                            _start_idx = clip_data.get('start_index', 0)
                            _end_idx = clip_data.get('end_index', 0)
                            _clip_lines_music = []
                            for _li in range(_start_idx, min(_end_idx + 1, len(raw_transcript))):
                                _clip_lines_music.append(raw_transcript[_li].text)
                            _clip_text_music = " ".join(_clip_lines_music)
                            _hook_music = raw_transcript[_start_idx].text if _start_idx < len(raw_transcript) else ""

                            job.message = f"Analyzing emotional tone for clip {i + 1}/{len(clips_data)}..."
                            emotion_data = analyze_clip_emotion(_clip_text_music, _hook_music, api_key, clip_id=clip_id)

                            job.message = f"Selecting local royalty-free background music for clip {i + 1}/{len(clips_data)}..."
                            music_file = fetch_elevenlabs_music(
                                emotion_data["music_description"],
                                duration,
                                clip_id,
                                emotion=emotion_data.get("emotion")
                            )

                            if music_file and os.path.exists(music_file):
                                # Load local music selection metadata
                                music_meta_path = os.path.join("output", "cache", f"music_metadata_{clip_id}.json")
                                if os.path.exists(music_meta_path):
                                    try:
                                        with open(music_meta_path, "r", encoding="utf-8") as mmf:
                                            music_meta = json.load(mmf)
                                            music_category_p25 = music_meta.get("music_category")
                                            music_file_p25 = music_meta.get("music_file")
                                            music_source = music_meta.get("music_source", "local_library")
                                            license_p25 = music_meta.get("license")
                                            license_id_p25 = music_meta.get("license_id")
                                            if "volume_pct" in music_meta:
                                                emotion_data["volume_pct"] = music_meta["volume_pct"]
                                    except Exception as mmf_err:
                                        logger.warning(f"Failed to load music metadata for {clip_id}: {mmf_err}")

                                job.message = f"Mixing music into clip {i + 1}/{len(clips_data)}..."
                                with_music_result = mix_music_into_clip(
                                    output_path,
                                    music_file,
                                    emotion_data["volume_pct"],
                                    emotion_data["fade_in_secs"],
                                    emotion_data["fade_out_secs"],
                                    duration,
                                    clip_id
                                )
                                with_music_filename = os.path.basename(with_music_result)
                                # Serve with-music version as default filename
                                if with_music_result != output_path:
                                    final_filename = with_music_filename
                                    logger.info(f"Clip {clip_id}: serving with-music version '{final_filename}'")
                                else:
                                    logger.warning(f"Clip {clip_id}: music mixing returned original — no music applied.")
                                    music_source = "none"
                                    emotion_data = None

                                # Phase 25 Layer 3 — Impact Sound Effects
                                if with_music_result != output_path:
                                    job.message = f"Adding cinematic impact SFX for clip {i + 1}/{len(clips_data)}..."
                                    try:
                                        from music_selector import add_impact_sounds
                                        impact_result = add_impact_sounds(
                                            with_music_result,
                                            _clip_text_music,
                                            _hook_music,
                                            clip_id,
                                            api_key,
                                            duration
                                        )
                                        with_music_result = impact_result["path"]
                                        final_filename = os.path.basename(with_music_result)
                                        audio_layers_p25 = impact_result.get("layers_applied", [])
                                        impact_count_p25 = impact_result.get("impact_count", 0)
                                        impact_detail_p25 = impact_result.get("impact_detail", [])
                                        logger.info(
                                            f"Clip {clip_id}: Phase 25 complete — "
                                            f"layers={audio_layers_p25}, impacts={impact_count_p25}"
                                        )
                                    except Exception as sfx_err:
                                        logger.error(f"Impact SFX failed for clip {clip_id}: {sfx_err}. Continuing.")
                                        audio_layers_p25 = ["ducking", "intro_build"]
                                        impact_count_p25 = 0
                                        impact_detail_p25 = []
                                else:
                                    audio_layers_p25 = []
                                    impact_count_p25 = 0
                                    impact_detail_p25 = []
                            else:
                                logger.info(f"Clip {clip_id}: no music file available. Skipping music mix.")
                                emotion_data = None
                                music_source = "none"
                                audio_layers_p25 = []
                                impact_count_p25 = 0
                                impact_detail_p25 = []

                        except Exception as music_err:
                            logger.error(f"Music pipeline failed for clip {clip_id}: {music_err}. Continuing without music.")
                            emotion_data = None
                            music_source = "none"
                            audio_layers_p25 = []
                            impact_count_p25 = 0
                            impact_detail_p25 = []

                        # -------------------------------------------------------
                        # Phase 26 — Like Prompt Overlay (Final Step)
                        # -------------------------------------------------------
                        like_overlay_added_p26 = False
                        job.message = f"Adding like prompt overlay for clip {i + 1}/{len(clips_data)}..."
                        try:
                            from overlays import add_like_overlay
                            overlay_result = add_like_overlay(with_music_result, clip_id, duration)
                            if overlay_result and os.path.exists(overlay_result):
                                with_music_result = overlay_result
                                final_filename = os.path.basename(with_music_result)
                                like_overlay_added_p26 = True
                                logger.info(f"Clip {clip_id}: Like prompt overlay successfully applied.")
                        except Exception as overlay_err:
                            logger.error(f"Like prompt overlay failed for clip {clip_id}: {overlay_err}. Continuing.")

                        clip_info = ClipInfo(
                            id=clip_id,
                            title=clip_data['title'],
                            reason=clip_data['reason'],
                            start_time=clip_data['start_time'],
                            end_time=clip_data['end_time'],
                            duration=duration,
                            filename=final_filename,
                            shorts_title=clip_data['shorts_title'],
                            shorts_description=clip_data['shorts_description'],
                            shorts_tags=clip_data['shorts_tags'],
                            virality_score=clip_data.get('virality_score', 0.0),
                            detailed_scores=clip_data.get('detailed_scores', {}),
                            experiment_id=clip_data.get('experiment_id', ''),
                            variant_id=clip_data.get('variant_id', ''),
                            scoring_version=clip_data.get('scoring_version', ''),
                            prompt_version=clip_data.get('prompt_version', ''),
                            weight_version=clip_data.get('weight_version', ''),
                            encoder_used=encoder_used,
                            boundary_quality=clip_data.get('boundary_quality'),
                            camera_qa=camera_qa_data,
                            subtitle_zone_detected=subs_detected,
                            subtitle_zone_height=subs_height,
                            upload_package=package,
                            emotion=emotion_data.get("emotion") if emotion_data else None,
                            energy_level=emotion_data.get("energy_level") if emotion_data else None,
                            music_description=emotion_data.get("music_description") if emotion_data else None,
                            volume_pct=emotion_data.get("volume_pct") if emotion_data else None,
                            music_source=music_source if music_source != "none" else None,
                            has_music=(music_source != "none" and emotion_data is not None),
                            music_category=music_category_p25,
                            music_file=music_file_p25,
                            license=license_p25,
                            license_id=license_id_p25,
                            audio_layers=audio_layers_p25,
                            impact_moments=impact_count_p25,
                            impact_moments_detail=impact_detail_p25 if impact_detail_p25 else None,
                            like_overlay_added=like_overlay_added_p26,
                        )
                        clips.append(clip_info)
                        
                        # Save clip metadata cache immediately
                        try:
                            with open(clip_metadata_path, "w", encoding="utf-8") as mf:
                                json.dump(clip_info.dict(), mf, indent=2)
                            logger.info(f"Saved clip {clip_id} metadata cache to disk.")
                        except Exception as cache_write_err:
                            logger.warning(f"Failed to write metadata cache for clip {clip_id}: {cache_write_err}")
                        
                        # Log to the analytics repository with all subtitle metrics
                        try:
                            from analytics_repository import db as analytics_db
                            analytics_db.save_clip_metadata(
                                video_id=video_id,
                                clip_id=clip_id,
                                virality_score=clip_data.get('virality_score', 0.0),
                                detailed_scores=clip_data.get('detailed_scores', {}),
                                experiment_id=clip_data.get('experiment_id'),
                                variant_id=clip_data.get('variant_id'),
                                scoring_version=clip_data.get('scoring_version'),
                                prompt_version=clip_data.get('prompt_version'),
                                weight_version=clip_data.get('weight_version'),
                                title=clip_data.get('title'),
                                reason=clip_data.get('reason'),
                                shorts_title=clip_data.get('shorts_title'),
                                shorts_description=clip_data.get('shorts_description'),
                                shorts_tags=clip_data.get('shorts_tags'),
                                duration=clip_data.get('duration'),
                                subtitle_style=resolved_style,
                                creator_preset=creator_preset,
                                words_per_chunk=words_per_chunk,
                                reading_speed=reading_speed,
                                highlight_count=highlight_count,
                                render_time_ms=render_time_ms,
                                ass_event_count=ass_event_count,
                                fallback_used=fallback_used,
                                subtitle_version="v16",
                                face_position=face_position,
                                start_time=clip_data.get('start_time'),
                                end_time=clip_data.get('end_time'),
                                start_index=clip_data.get('start_index'),
                                end_index=clip_data.get('end_index'),
                                upload_package=package,
                                emotion=emotion_data.get("emotion") if emotion_data else None,
                                energy_level=emotion_data.get("energy_level") if emotion_data else None,
                                music_description=emotion_data.get("music_description") if emotion_data else None,
                                volume_pct=emotion_data.get("volume_pct") if emotion_data else None,
                                music_source=music_source if music_source != "none" else None,
                                has_music=(music_source != "none" and emotion_data is not None)
                            )
                            logger.info(f"Saved clip {clip_id} metadata and subtitle analytics to database.")
                        except Exception as db_err:
                            logger.warning(f"Failed to save clip {clip_id} metadata to analytics database: {db_err}")
                except Exception as clip_err:
                    logger.error(f"Failed to process clip {clip_data.get('title', 'Unknown')}: {clip_err}", exc_info=True)
                    continue
                    
            # Overwrite clip_generation_report.md to reflect final Camera QA exclusions
            if os.path.exists(artifact_dir):
                report_path = os.path.join(artifact_dir, "clip_generation_report.md")
                skip_reasons_md = "\n".join(f"- {r}" for r in skip_reasons) if skip_reasons else "*None*"
                
                approved_details_list = []
                for idx, c in enumerate(clips):
                    approved_details_list.append(f"""### {idx+1}. {c.title}
- **Time Range**: {c.start_time}s - {c.end_time}s (duration: {c.duration:.2f}s)
- **Virality Score**: {c.virality_score}/10
- **Scoring Reasoning**: {c.reason}
- **Shorts Title**: `{c.shorts_title}`
- **Description**: {c.shorts_description}
""")
                clips_details_md = "\n".join(approved_details_list) if approved_details_list else "*No clips passed all quality and Camera QA bars.*"
                
                rejected_details_list = []
                for c_data, qa in rejected_by_camera_qa:
                    failures = []
                    if qa:
                        vis = qa.get("speaker_visibility_pct", 100.0)
                        if vis < 90.0:
                            failures.append(f"Speaker Visibility: {vis:.1f}% (failed threshold >= 90% by {90.0 - vis:.1f}%)")
                        switches = qa.get("track_switches", 0)
                        if switches > 5:
                            failures.append(f"Track Switches: {switches} (failed threshold <= 5 by {switches - 5})")
                        mov = qa.get("avg_movement_per_frame", 0.0)
                        if mov > 12.0:
                            failures.append(f"Average Crop Movement: {mov:.2f}px/frame (failed threshold <= 12.0px/frame by {mov - 12.0:.2f}px/frame)")
                        face_loss = qa.get("max_consecutive_face_lost_frames", 0)
                        if face_loss > 240:
                            failures.append(f"Max Consecutive Face Loss: {face_loss} frames (failed threshold <= 240 frames by {face_loss - 240} frames)")
                    else:
                        failures.append("No camera QA metrics available")
                    
                    reason_str = "; ".join(failures)
                    rejected_details_list.append(f"- **{c_data['title']}** (Time: {c_data['start_time']}s - {c_data['end_time']}s): Failed Camera QA ({reason_str})")
                
                rejected_by_camera_qa_md = "\n".join(rejected_details_list) if rejected_details_list else "*None*"
                
                avg_approved_virality = sum(c.virality_score for c in clips) / len(clips) if clips else 0.0
                
                report_content = f"""# Clip Generation Report

This report summarizes the clip filtering pipeline stages and details how many clips were scouted, curated, and validated with their post-curation virality scores.

## Summary Metrics

- **Requested Clips**: {num_clips if num_clips is not None else 'Dynamic'}
- **Scout Found Candidates**: {scout_count}
- **Curator Selected (Passed Quality Bar)**: {curator_count}
- **After Deduplication/Validation**: {dedup_count}
- **Final Exported Clips**: {len(clips)}
- **Average Approved Virality Score**: {avg_approved_virality:.2f}/10

## Approved Clips (Sorted by Virality Score)

{clips_details_md}

## Rejected by Camera QA

{rejected_by_camera_qa_md}

## Discarded / Skipped Clips Details (LLM & Dedup)

{skip_reasons_md}
"""
                try:
                    with open(report_path, "w", encoding="utf-8") as f:
                        f.write(report_content)
                except Exception as write_err:
                    logger.warning(f"Could not overwrite clip_generation_report.md artifact: {write_err}")
            
            duration_step4 = time.perf_counter() - t_start_step4
            
            # Write performance_report.md
            if os.path.exists(artifact_dir):
                perf_report_path = os.path.join(artifact_dir, "performance_report.md")
                clip_timings_md = "\n".join(f"- **{title}**: {dur:.2f}s" for title, dur in clip_timings)
                perf_content = f"""# Performance Report

This report breaks down the execution times for each phase of the ClipMind pipeline.

## Pipeline Duration Breakdown

| Stage | Duration (seconds) | Description |
|---|---|---|
| **Step 1: Fetch Transcript** | {duration_step1:.2f}s | Retrieving YouTube transcript and parsing |
| **Step 2: Analyze with Gemini** | {duration_step2:.2f}s | Multi-agent analysis, scoring, and curation |
| **Step 3: Download Video** | {duration_step3:.2f}s | Fetching high-quality source video |
| **Step 4: Extract Clips (FFmpeg)** | {duration_step4:.2f}s | Slicing, face-tracking, and ASS subtitles burn |
| **Total Pipeline Time** | {duration_step1 + duration_step2 + duration_step3 + duration_step4:.2f}s | Full end-to-end execution |

## FFmpeg Clip Extraction Times

{clip_timings_md}
"""
                try:
                    with open(perf_report_path, "w", encoding="utf-8") as f:
                        f.write(perf_content)
                except Exception as write_err:
                    logger.warning(f"Could not write performance_report.md artifact: {write_err}")
                
                # Write boundary_quality_report.md
                bq_report_path = os.path.join(artifact_dir, "boundary_quality_report.md")
                rows = []
                total_completeness = 0.0
                for c in clips:
                    bq = c.boundary_quality or {}
                    start_clean = "✅ Clean" if bq.get("start_clean") else "❌ Conjunction/Filler"
                    end_clean = "✅ Punctuation" if bq.get("end_clean") else "❌ No Punctuation"
                    audio_refined = "✅ Refined" if bq.get("audio_refined") else "❌ None"
                    score = bq.get("story_completeness_score", 0.0)
                    total_completeness += score
                    
                    rows.append(
                        f"| {c.title} | {start_clean} | {end_clean} | {audio_refined} | {score}/10 |"
                    )
                    
                avg_score = (total_completeness / len(clips)) if clips else 0.0
                rows_md = "\n".join(rows)
                
                bq_content = f"""# Boundary Quality & Story Completeness Report

This report summarizes the boundary cleanliness, audio alignment, and story completeness for each generated YouTube Short.

## Overall Summary

- **Total Clips Evaluated**: {len(clips)}
- **Average Story Completeness Score**: **{avg_score:.1f}/10**

## Per-Clip Quality Metrics

| Clip Title | Start Boundary | End Boundary | Audio Silence Refinement | Story Completeness Score |
|---|---|---|---|---|
{rows_md}
"""
                try:
                    with open(bq_report_path, "w", encoding="utf-8") as f:
                        f.write(bq_content)
                except Exception as write_err:
                    logger.warning(f"Could not write boundary_quality_report.md artifact: {write_err}")
                
                # Write camera_failure_report.md
                cam_report_path_local = "output/camera_failure_report.md"
                cam_report_path_artifact = os.path.join(artifact_dir, "camera_failure_report.md") if artifact_dir else None
                
                cam_rows = []
                for c in clips:
                    qa = c.camera_qa or {}
                    if not qa:
                        continue
                    vis = qa.get("speaker_visibility_pct", 100.0)
                    switches = qa.get("track_switches", 0)
                    lost = qa.get("lost_tracks", 0)
                    freezes = qa.get("freeze_events", 0)
                    mov = qa.get("avg_movement_per_frame", 0.0)
                    max_lost_f = qa.get("max_consecutive_face_lost_frames", 0)
                    passed = "✅ PASS" if qa.get("qa_passed") else "❌ FAIL"
                    subs_det = "Yes" if c.subtitle_zone_detected else "No"
                    subs_h = f"{c.subtitle_zone_height}px"
                    crop_adj = "Yes" if c.subtitle_zone_detected else "No"
                    
                    cam_rows.append(
                        f"| {c.title} | {vis:.1f}% | {switches} | {lost} | {freezes} | {mov:.2f}px | {max_lost_f} | {subs_det} | {subs_h} | {crop_adj} | **{passed}** |"
                    )
                
                if cam_rows:
                    cam_rows_md = "\n".join(cam_rows)
                    cam_content = f"""# Camera Tracking Quality Assurance Report

This report summarizes the camera stabilization, active speaker visibility, and motion smoothing quality metrics for each generated YouTube Short.

## QA Thresholds
- **Speaker Visibility**: $\ge 90\%$ (Active speaker must be inside the crop box)
- **Track Switches**: $\le 5$ (To prevent rapid camera panning/switches)
- **Average Crop Movement**: $\le 12.0$ px/frame (To prevent jitter)
- **Max Consecutive Face Loss**: $\le 60$ frames / 2.0 seconds (To prevent drift)

## Per-Clip Quality Metrics

| Clip Title | Speaker Visibility | Track Switches | Lost Tracks | Freeze Events | Avg Movement | Max Face Loss (frames) | Subtitles Detected | Subtitle Height | Crop Adjusted | QA Status |
|---|---|---|---|---|---|---|---|---|---|---|
{cam_rows_md}
"""
                    try:
                        os.makedirs("output", exist_ok=True)
                        with open(cam_report_path_local, "w", encoding="utf-8") as f:
                            f.write(cam_content)
                        if cam_report_path_artifact:
                            with open(cam_report_path_artifact, "w", encoding="utf-8") as f:
                                f.write(cam_content)
                    except Exception as write_err:
                        logger.warning(f"Could not write camera_failure_report.md: {write_err}")
                
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
            
        finally:
            # Delete source video to save space if it's not cached
            if video_path and os.path.exists(video_path):
                if "output" in video_path and "cache" in video_path:
                    logger.info(f"Preserving cached source video: {video_path}")
                else:
                    try:
                        os.remove(video_path)
                        logger.info(f"Cleaned up temporary source video file: {video_path}")
                    except Exception as e:
                        logger.warning(f"Could not remove temporary source video file {video_path}: {e}")
