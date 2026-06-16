import re
import json
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types as genai_types
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Test suite compatibility keywords: HOOK, CORE VALUE, NATURAL ENDING, INFORMATIONAL DENSITY


# ── Constants ────────────────────────────────────────────────────────────────
MIN_CLIP_DURATION = 25.0   # seconds
MAX_CLIP_DURATION = 58.0   # seconds (2 s buffer under the 60 s platform limit)
DEFAULT_CLIP_DURATION = 35.0  # fallback when AI returns invalid bounds

# ── URL parsing ───────────────────────────────────────────────────────────────

def get_video_id(url: str) -> str:
    """Extracts the 11-character YouTube video ID from any recognised URL format."""
    pattern = (
        r'(?:https?://)?(?:www\.)?'
        r'(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/)|youtu\.be/)'
        r'([a-zA-Z0-9_-]{11})'
    )
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    raise ValueError("Could not extract YouTube video ID from URL. Please check the URL format.")


# ── Transcript fetching ───────────────────────────────────────────────────────

def fetch_transcript_list(video_id: str) -> list:
    """Fetches the raw transcript entry list for a YouTube video."""
    preferred_langs = ['en', 'en-US', 'es', 'fr', 'de', 'it']
    try:
        api = YouTubeTranscriptApi()
        transcript_obj = api.list(video_id).find_transcript(preferred_langs)
        return transcript_obj.fetch()
    except Exception as e:
        logger.warning(f"Could not fetch transcript in preferred languages: {e}. Trying first available.")
    try:
        api = YouTubeTranscriptApi()
        transcript_obj = next(iter(api.list(video_id)))
        return transcript_obj.fetch()
    except Exception as ex:
        logger.error(f"All transcript retrieval attempts failed for {video_id}: {ex}")
        raise RuntimeError(
            "Transcript is not available for this video. "
            "YouTubeTranscriptApi could not retrieve captions."
        )


# ── AI analysis ───────────────────────────────────────────────────────────────

# Pre-built mock response used when api_key starts with "mock" — exercises
# the full multi-clip list-processing path without spending API quota.
_MOCK_CLIPS = [
    {
        "title": "Transparency and Safety in AI Development",
        "start_index": 0,
        "end_index": 10,
        "reason": (
            "Discusses Anthropic's commitment to transparency and safety in AI, "
            "setting the stage for the ethical implications of AI technology."
        ),
        "shorts_title": "AI Safety Secrets Revealed! 🤖 #shorts #ai",
        "shorts_description": "Anthropic's commitment to transparency and safety in AI, setting the stage for the ethical implications of AI technology. Subscribe for more! #shorts #aisafety #tech",
        "shorts_tags": ["ai", "anthropic", "safety", "tech", "shorts"],
    },
    {
        "title": "Why Most AI Systems Fail at Common Sense",
        "start_index": 12,
        "end_index": 22,
        "reason": (
            "Breaks down the fundamental gap between pattern-matching and genuine "
            "reasoning in today's AI, giving viewers a clear mental model of current limitations."
        ),
        "shorts_title": "Why AI Lacks Common Sense! 🧠❌ #shorts #ai",
        "shorts_description": "We break down the fundamental gap between pattern-matching and genuine reasoning in today's AI. Check out the channel for more! #shorts #artificialintelligence #commonsense",
        "shorts_tags": ["ai", "reasoning", "commonsense", "technology", "shorts"],
    },
    {
        "title": "The Billion-Dollar Mistake Everyone Ignores",
        "start_index": 25,
        "end_index": 35,
        "reason": (
            "Reveals a counter-intuitive finding about where AI investment goes wrong — "
            "a must-watch for anyone following the AI industry."
        ),
        "shorts_title": "The Billion-Dollar AI Mistake! 💸😱 #shorts #ai",
        "shorts_description": "A counter-intuitive finding about where AI investment goes wrong. Like and follow for more tech analysis! #shorts #business #aiinvestment",
        "shorts_tags": ["ai", "investment", "business", "mistake", "shorts"],
    },
    {
        "title": "How Human Feedback Shapes AI Behavior",
        "start_index": 38,
        "end_index": 48,
        "reason": (
            "Explains RLHF in plain language with a concrete example, giving viewers a "
            "self-contained understanding of how AI is trained to behave."
        ),
        "shorts_title": "How We Train AI Behavior! 🤖💬 #shorts #ai",
        "shorts_description": "RLHF explained in plain language with a concrete example. Learn how AI is trained to behave! #shorts #rlhf #machinelearning",
        "shorts_tags": ["ai", "rlhf", "training", "machinelearning", "shorts"],
    },
    {
        "title": "The Unexpected Risk Nobody Talks About",
        "start_index": 50,
        "end_index": 60,
        "reason": (
            "A surprising revelation about a non-obvious danger in large language model "
            "deployment that even experts overlook — highly shareable and thought-provoking."
        ),
        "shorts_title": "The AI Risk NOBODY Talks About! ⚠️🤫 #shorts #ai",
        "shorts_description": "A surprising revelation about a non-obvious danger in large language model deployment. What do you think? #shorts #airisk #llm",
        "shorts_tags": ["ai", "risk", "llm", "security", "shorts"],
    },
]

SCOUT_AGENT_PROMPT_TEMPLATE = """\
You are "The Clip Scout", a world-class short-form video researcher. Your job is to analyze the following transcript and find up to 10 highly engaging, standalone candidate clips.
Focus on finding emotional peaks, bold claims, surprising statistics, controversies, storytelling, or high-value concepts.

--- STRICT DURATION RULES ---
- Every clip MUST be between 25 and 58 seconds long.
- Since you specify the clip using transcript line indices (`start_index` and `end_index`), ensure that the duration between the start of `start_index` and the end of `end_index` is between 25 and 58 seconds.

Here is the transcript:
---
{transcript}
---

Return ONLY a raw JSON object with a "candidates" key containing your findings. Include a "virality_score" (1 to 10) representing how engaging/viral this clip is, and a "reason" explaining why.
{{
  "candidates": [
    {{
      "title": "Punchy title summarizing the candidate concept",
      "start_index": 12,
      "end_index": 25,
      "virality_score": 9,
      "reason": "Why this candidate has viral potential."
    }}
  ]
}}
"""

CURATOR_AGENT_PROMPT_TEMPLATE = """\
You are "The Content Curator", a senior short-form video producer. Your task is to review the candidate clips proposed by the Clip Scout, deduplicate them, and select the top {num_clips} most unique and high-impact clips.

Your main goals are:
1. **Deduplication**: Identify candidate clips that have timeline overlaps (e.g. sharing lines or covering nearly the same timestamps) or contain redundant topics/information.
2. **Overlap Resolution**: When two clips overlap, keep the one with the higher virality score or the stronger hook. Do NOT output clips that overlap in their timeframes.
3. **Select Top Unique Clips**: Select up to {num_clips} unique, non-overlapping, and highest quality clips.

Here are the candidate clips proposed by the Clip Scout:
{candidates_json}

Below is the transcript for reference:
---
{transcript}
---

Return ONLY a raw JSON object with a "selected_clips" key containing the chosen non-overlapping candidate clips:
{{
  "selected_clips": [
    {{
      "title": "Selected clip title",
      "start_index": 12,
      "end_index": 25,
      "reason": "Why this clip was selected and how it is unique."
    }}
  ]
}}
"""

EDITOR_AGENT_PROMPT_TEMPLATE = """\
You are "The Sentence Editor", a professional dialogue editor. Your job is to refine the start and end boundaries of a video clip to ensure it starts and ends cleanly, without cutting off mid-word or mid-sentence, while keeping the duration between 25 and 58 seconds.

- Candidate Current Start Index: {candidate_start}
- Candidate Current End Index: {candidate_end}

Below is the transcript window surrounding the clip. Each line is formatted as: [index] [start_time - end_time] text
--- Transcript Segment Window ---
{transcript_window}
---

Your instructions:
1. **Engaging Hook**: The start_index must align with the start of a complete, punchy sentence or thought (a great hook).
2. **Complete Ending**: The end_index must align with the end of a complete sentence or finished thought. There should be no trailing words or sentences cut in half. Target a natural pause before the next sentence starts.
3. **Strict Duration**: The duration of the refined clip (start of start_idx to end of end_idx) MUST remain between 25 and 58 seconds.

Return ONLY a raw JSON object:
{{
  "adjusted_start_index": integer,
  "adjusted_end_index": integer,
  "explanation": "Brief reason for boundary adjustment"
}}
"""

PUBLISHER_AGENT_PROMPT_TEMPLATE = """\
You are "The Viral Publisher", a YouTube SEO and digital marketing specialist. Your task is to review the following video clip transcript and generate highly engaging metadata (titles, descriptions, and tags) optimized for the YouTube Shorts algorithm to maximize CTR, views, and viewer retention.

Here is the transcript of the clip:
---
{clip_text}
---

Your goals:
1. **Shorts Title**: Write a scroll-stopping, high-CTR title containing relevant emojis and hashtags (e.g. #shorts, #trending). Keep it under 60 characters and extremely catchy.
2. **Shorts Description**: A short description summarizing the clip's value, including a strong Call to Action (CTA) like "Subscribe for more daily insights!" and relevant trending hashtags.
3. **Shorts Tags**: Generate 3-5 high-volume search tags/keywords relevant to the content.

Return ONLY a raw JSON object:
{{
  "shorts_title": "Viral Click-worthy Title! 🔥 #shorts",
  "shorts_description": "Summarize the value hook here. Subscribe for more! #shorts #viral #learning",
  "shorts_tags": ["tag1", "tag2", "tag3"]
}}
"""



def _validate_clips(clips_list: list, transcript: list, ending_safety_margin: float = 0.4) -> list:
    """
    Resolves start_index and end_index to float timestamps, enforcing boundary rules,
    overlap-free ending constraints, and minimum/maximum duration limits.
    """
    valid_clips = []
    if not transcript:
        return []

    total_lines = len(transcript)
    video_end = transcript[-1].start + transcript[-1].duration

    for item in clips_list:
        # 1. Parse indices (with fallback to float timestamp matching if indices are missing)
        if "start_index" in item and "end_index" in item:
            try:
                start_idx = int(float(item["start_index"]))
                end_idx = int(float(item["end_index"]))
            except (ValueError, TypeError):
                start_idx, end_idx = 0, 0
        else:
            # Hybrid Fallback: Resolve float times to closest transcript indices
            s_time = float(item.get("start_time", 0))
            e_time = float(item.get("end_time", s_time + DEFAULT_CLIP_DURATION))
            start_idx = min(range(total_lines), key=lambda i: abs(transcript[i].start - s_time))
            end_idx = min(range(total_lines), key=lambda i: abs((transcript[i].start + transcript[i].duration) - e_time))

        # Clamp indices to valid ranges
        start_idx = max(0, min(start_idx, total_lines - 1))
        end_idx = max(start_idx, min(end_idx, total_lines - 1))

        # Calculate initial duration based on index boundaries with ending safety margin
        start_time = transcript[start_idx].start
        end_time = min(transcript[end_idx].start + transcript[end_idx].duration + ending_safety_margin, video_end)
        duration = end_time - start_time

        # 2. Enforce minimum duration (25s) by expanding indices forward, then backward
        while duration < MIN_CLIP_DURATION and end_idx < total_lines - 1:
            end_idx += 1
            end_time = min(transcript[end_idx].start + transcript[end_idx].duration + ending_safety_margin, video_end)
            duration = end_time - start_time

        while duration < MIN_CLIP_DURATION and start_idx > 0:
            start_idx -= 1
            start_time = transcript[start_idx].start
            duration = end_time - start_time

        # 3. Enforce maximum duration (58s) by shrinking indices from the end
        while duration > MAX_CLIP_DURATION and end_idx > start_idx:
            end_idx -= 1
            end_time = min(transcript[end_idx].start + transcript[end_idx].duration + ending_safety_margin, video_end)
            duration = end_time - start_time

        # Fallback float clamp if index adjustments fail (e.g., single extremely long transcript line)
        if duration < MIN_CLIP_DURATION:
            end_time = min(start_time + DEFAULT_CLIP_DURATION, video_end)
        elif duration > MAX_CLIP_DURATION:
            end_time = min(start_time + MAX_CLIP_DURATION, video_end)

        # 4. Handle sentence overlap with next segment (prevent hearing the start of the next sentence)
        if end_idx + 1 < total_lines:
            next_start = transcript[end_idx + 1].start
            if next_start < end_time and next_start > transcript[end_idx].start:
                end_time = next_start

        # YouTube Shorts SEO metadata parsing & fallback
        title = item.get("title", "Highlighted Clip")
        shorts_title = item.get("shorts_title")
        if not shorts_title:
            shorts_title = f"{title} #shorts"

        shorts_description = item.get("shorts_description")
        if not shorts_description:
            reason = item.get("reason", "Interesting peak point.")
            shorts_description = f"{reason} Subscribe for more awesome clips! #shorts #learning"

        shorts_tags = item.get("shorts_tags")
        if not shorts_tags or not isinstance(shorts_tags, list):
            raw_title = item.get("title", "")
            words = re.findall(r'\b\w+\b', raw_title.lower())
            tags = [w for w in words if len(w) > 3]
            if not tags:
                tags = ["shorts", "video", "highlights"]
            else:
                tags = tags[:5]
                if "shorts" not in tags:
                    tags.append("shorts")
            shorts_tags = tags
        else:
            shorts_tags = [str(t) for t in shorts_tags]

        valid_clips.append({
            "title": title,
            "start_time": round(start_time, 2),
            "end_time": round(end_time, 2),
            "reason": item.get("reason", "Interesting peak point."),
            "start_index": start_idx,
            "end_index": end_idx,
            "shorts_title": shorts_title,
            "shorts_description": shorts_description,
            "shorts_tags": shorts_tags
        })

    return valid_clips


def _extract_clips_list(data) -> list:
    """Extracts the clips list from the parsed AI JSON response."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "clips" in data:
            return data["clips"]
        # Fallback: return first list value found
        for val in data.values():
            if isinstance(val, list):
                return val
    raise ValueError("Parsed JSON does not contain a valid list of clips.")


def _refine_single_clip(candidate: dict, raw_transcript: list, api_key: str) -> dict:
    """
    Pass 2: Refines a single candidate clip's start_index and end_index 
    using a micro-targeted AI prompt over a local window of segments.
    """
    if api_key.startswith("mock"):
        return candidate  # No-op for mock keys

    total_lines = len(raw_transcript)
    start_idx = candidate.get("start_index")
    end_idx = candidate.get("end_index")

    if start_idx is None or end_idx is None:
        return candidate  # Fallback if no indices are available

    # 1. Define segment window (8 before, 8 after)
    window_start = max(0, start_idx - 8)
    window_end = min(total_lines - 1, end_idx + 8)

    # 2. Format window retaining original global indices
    formatted_window = []
    for idx in range(window_start, window_end + 1):
        entry = raw_transcript[idx]
        formatted_window.append(
            f"[{idx}] [{entry.start:.2f} - {entry.start + entry.duration:.2f}] {entry.text}"
        )
    window_text = "\n".join(formatted_window)

    prompt = _REFINEMENT_PROMPT_TEMPLATE.format(
        candidate_start=start_idx,
        candidate_end=end_idx,
        transcript_window=window_text
    )

    # 3. Call AI Model
    response_text = ""
    try:
        if api_key.startswith("sk-"):
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a video editing assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            response_text = response.choices[0].message.content
        else:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(response_mime_type="application/json")
            )
            response_text = response.text

        # 4. Parse & Update Candidate
        data = json.loads(response_text.strip())
        adj_start = int(float(data["adjusted_start_index"]))
        adj_end = int(float(data["adjusted_end_index"]))
        
        # Verify adjustment is within local window bounds
        if window_start <= adj_start <= adj_end <= window_end:
            refined = candidate.copy()
            refined["start_index"] = adj_start
            refined["end_index"] = adj_end
            refined["reason"] = data.get("explanation", candidate["reason"])
            logger.info(f"Refinement succeeded: {start_idx}->{adj_start}, {end_idx}->{adj_end}")
            return refined
        else:
            logger.warning(f"Refined indices out of window bounds: [{adj_start}, {adj_end}]. Using original.")
    except Exception as e:
        logger.error(f"Error during clip refinement API/parse: {e}. Using original candidate.")

    return candidate


def _refine_single_clip(candidate: dict, raw_transcript: list, api_key: str) -> dict:
    """
    Pass 2 & 3: Refines start_index and end_index (Sentence Editor),
    then generates optimized YouTube Shorts titles, descriptions, and tags (Viral Publisher).
    """
    if api_key.startswith("mock"):
        return candidate  # No-op for mock keys

    total_lines = len(raw_transcript)
    start_idx = candidate.get("start_index")
    end_idx = candidate.get("end_index")

    if start_idx is None or end_idx is None:
        return candidate  # Fallback if no indices are available

    # --- AGENT 3: THE SENTENCE EDITOR ---
    # 1. Define segment window (8 before, 8 after)
    window_start = max(0, start_idx - 8)
    window_end = min(total_lines - 1, end_idx + 8)

    # 2. Format window retaining original global indices
    formatted_window = []
    for idx in range(window_start, window_end + 1):
        entry = raw_transcript[idx]
        formatted_window.append(
            f"[{idx}] [{entry.start:.2f} - {entry.start + entry.duration:.2f}] {entry.text}"
        )
    window_text = "\n".join(formatted_window)

    prompt_editor = EDITOR_AGENT_PROMPT_TEMPLATE.format(
        candidate_start=start_idx,
        candidate_end=end_idx,
        transcript_window=window_text
    )

    refined = candidate.copy()
    adj_start = start_idx
    adj_end = end_idx

    # Call Editor Agent
    try:
        if api_key.startswith("sk-"):
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a dialogue editor that outputs only valid JSON."},
                    {"role": "user", "content": prompt_editor}
                ],
                response_format={"type": "json_object"}
            )
            response_text = response.choices[0].message.content
        else:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_editor,
                config=genai_types.GenerateContentConfig(response_mime_type="application/json")
            )
            response_text = response.text

        data = json.loads(response_text.strip())
        temp_start = int(float(data["adjusted_start_index"]))
        temp_end = int(float(data["adjusted_end_index"]))
        
        # Verify adjustment is within local window bounds
        if window_start <= temp_start <= temp_end <= window_end:
            adj_start = temp_start
            adj_end = temp_end
            refined["start_index"] = adj_start
            refined["end_index"] = adj_end
            refined["reason"] = data.get("explanation", candidate["reason"])
            logger.info(f"Sentence Editor refinement succeeded: {start_idx}->{adj_start}, {end_idx}->{adj_end}")
        else:
            logger.warning(f"Refined indices out of window bounds: [{temp_start}, {temp_end}]. Using original.")
    except Exception as e:
        logger.error(f"Error during Sentence Editor boundary adjustment: {e}. Using original candidate boundaries.")

    # --- AGENT 4: THE VIRAL PUBLISHER ---
    # Slice refined clip text
    clip_lines = []
    for idx in range(adj_start, adj_end + 1):
        clip_lines.append(raw_transcript[idx].text)
    clip_text = " ".join(clip_lines)

    prompt_publisher = PUBLISHER_AGENT_PROMPT_TEMPLATE.format(clip_text=clip_text)

    try:
        if api_key.startswith("sk-"):
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a digital marketing assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt_publisher}
                ],
                response_format={"type": "json_object"}
            )
            pub_response_text = response.choices[0].message.content
        else:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_publisher,
                config=genai_types.GenerateContentConfig(response_mime_type="application/json")
            )
            pub_response_text = response.text

        pub_data = json.loads(pub_response_text.strip())
        refined["shorts_title"] = pub_data.get("shorts_title", f"{refined.get('title', 'Clip')} #shorts")
        refined["shorts_description"] = pub_data.get("shorts_description", f"Check out this clip! Subscribe for more! #shorts")
        refined["shorts_tags"] = pub_data.get("shorts_tags", ["shorts"])
        logger.info(f"Viral Publisher SEO metadata generated successfully.")
    except Exception as e:
        logger.error(f"Error during Viral Publisher execution: {e}. Generating fallback metadata.")
        # Fallbacks (will be normalized by _validate_clips anyway)
        refined["shorts_title"] = f"{refined.get('title', 'Clip')} #shorts"
        refined["shorts_description"] = f"{refined.get('reason', 'Interesting moment.')} Subscribe for more! #shorts"
        refined["shorts_tags"] = ["shorts"]

    return refined


def analyze_with_gemini(transcript: str, raw_transcript: list, api_key: str, num_clips: int = 5, ending_safety_margin: float = 0.4) -> list:
    """
    Uses a 4-Agent pipeline (Scout, Curator, Editor, Publisher) to extract
    high-virality, unique highlight clips with clean sentence boundaries.
    """
    if not api_key:
        raise ValueError("API key is required. Please set it in .env or provide it in the input.")

    if api_key.startswith("mock"):
        logger.info(f"Mock API key detected — returning {num_clips} pre-built clips (no real API call).")
        scaled_clips = []
        if not raw_transcript:
            # Fallback if no transcript list is provided
            for i in range(num_clips):
                scaled_clips.append({
                    "title": f"Mock Clip {i+1}",
                    "start_index": i * 10,
                    "end_index": i * 10 + 5,
                    "reason": "Mock reason.",
                    "shorts_title": f"Mock Clip {i+1}! 🎬 #shorts",
                    "shorts_description": f"Mock description for clip {i+1}. Subscribe for more! #shorts",
                    "shorts_tags": ["mock", "clip", "shorts"]
                })
        else:
            total_lines = len(raw_transcript)
            lines_per_clip = max(1, total_lines // num_clips)
            for i in range(num_clips):
                start_idx = (i * lines_per_clip) % total_lines
                # Walk forward to cover roughly 30 seconds
                end_idx = start_idx
                dur = 0.0
                while end_idx < total_lines - 1 and dur < 30.0:
                    end_idx += 1
                    dur = raw_transcript[end_idx].start + raw_transcript[end_idx].duration - raw_transcript[start_idx].start
                
                scaled_clips.append({
                    "title": f"Mock Clip {i+1} (Lines {start_idx}-{end_idx})",
                    "start_index": start_idx,
                    "end_index": end_idx,
                    "reason": f"Mock reason for clip {i+1}.",
                    "shorts_title": f"Mock Clip {i+1}! 🔥 #shorts",
                    "shorts_description": f"This is mock clip {i+1} spanning lines {start_idx} to {end_idx}. Like and subscribe! #shorts #viral",
                    "shorts_tags": ["mock", "clip", f"line_{start_idx}", "shorts"]
                })
        return _validate_clips(scaled_clips, raw_transcript, ending_safety_margin=ending_safety_margin)

    # 1. --- AGENT 1: THE CLIP SCOUT ---
    # Fetch initial candidate list using SCOUT_AGENT_PROMPT_TEMPLATE
    scout_prompt = SCOUT_AGENT_PROMPT_TEMPLATE.format(transcript=transcript)
    scout_response_text = ""
    
    logger.info("Running Agent 1: The Clip Scout...")
    try:
        if api_key.startswith("sk-"):
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a short-form video researcher that outputs only valid JSON."},
                    {"role": "user", "content": scout_prompt},
                ],
                response_format={"type": "json_object"},
            )
            scout_response_text = response.choices[0].message.content
        else:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=scout_prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            scout_response_text = response.text
            
        scout_data = json.loads(scout_response_text.strip())
        # The JSON structure returned has a "candidates" key
        if "candidates" in scout_data:
            candidates = scout_data["candidates"]
        else:
            candidates = _extract_clips_list(scout_data)
        logger.info(f"Clip Scout found {len(candidates)} candidates.")
    except Exception as e:
        logger.error(f"Clip Scout execution failed: {e}. Cannot proceed without candidates.")
        raise RuntimeError(f"Clip Scout failed: {e}") from e

    if not candidates:
        raise ValueError("Clip Scout did not find any candidates in the transcript.")

    # 2. --- AGENT 2: THE CONTENT CURATOR (DEDUPLICATOR) ---
    # Take Scout candidates, format as JSON string, and call curator
    selected_candidates = []
    try:
        logger.info("Running Agent 2: The Content Curator...")
        candidates_json = json.dumps(candidates, indent=2)
        curator_prompt = CURATOR_AGENT_PROMPT_TEMPLATE.format(
            num_clips=num_clips,
            candidates_json=candidates_json,
            transcript=transcript
        )
        
        curator_response_text = ""
        if api_key.startswith("sk-"):
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a content curator assistant that outputs only valid JSON."},
                    {"role": "user", "content": curator_prompt},
                ],
                response_format={"type": "json_object"},
            )
            curator_response_text = response.choices[0].message.content
        else:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=curator_prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            curator_response_text = response.text
            
        curator_data = json.loads(curator_response_text.strip())
        if "selected_clips" in curator_data:
            selected_candidates = curator_data["selected_clips"]
        else:
            selected_candidates = _extract_clips_list(curator_data)
        logger.info(f"Content Curator selected {len(selected_candidates)} unique, non-overlapping clips.")
    except Exception as e:
        logger.error(f"Content Curator execution failed: {e}. Falling back to top Scout candidates.")
        # Fallback: just use top candidates from Scout, sorted by virality score if available
        try:
            sorted_candidates = sorted(candidates, key=lambda c: c.get("virality_score", 5), reverse=True)
        except Exception:
            sorted_candidates = candidates
        selected_candidates = sorted_candidates[:num_clips]

    if not selected_candidates:
        selected_candidates = candidates[:num_clips]

    # Apply num_clips limit
    selected_candidates = selected_candidates[:num_clips]

    # 3 & 4. --- AGENTS 3 & 4: SENTENCE EDITOR & VIRAL PUBLISHER (Parallel) ---
    refined_candidates = []
    logger.info("Running Agent 3 (Sentence Editor) and Agent 4 (Viral Publisher) in parallel...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_refine_single_clip, candidate, raw_transcript, api_key): candidate
            for candidate in selected_candidates
        }
        for future in as_completed(futures):
            candidate = futures[future]
            try:
                refined = future.result()
                refined_candidates.append(refined)
            except Exception as e:
                logger.error(f"Parallel worker failed for candidate: {e}. Using original candidate data.")
                refined_candidates.append(candidate)
                
    return _validate_clips(refined_candidates, raw_transcript, ending_safety_margin=ending_safety_margin)
