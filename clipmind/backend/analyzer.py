import re
import json
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types as genai_types
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

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

_ANALYSIS_PROMPT_TEMPLATE = """\
You are a world-class short-form video producer specializing in creating viral, \
highly educational clips from long-form YouTube content.
Your task is to scan the transcript below and extract up to {num_clips} candidate clips that will \
perform exceptionally well as standalone short videos.

--- STRICT DURATION RULES ---
- Every clip MUST be between 25 and 58 seconds long.
- Since you will specify the clip using transcript line indices (`start_index` and `end_index`), ensure that the duration between the start of `start_index` and the end of `end_index` is between 25 and 58 seconds.
- Do not select indices that would result in a clip shorter than 25 seconds or longer than 58 seconds.

--- SENTENCE BOUNDARY RULES ---
- You MUST return the 0-based transcript line numbers (indices) `start_index` and `end_index` for each clip.
- The `start_index` MUST correspond to the first line of a complete sentence or thought (a great hook).
- The `end_index` MUST correspond to the last line of that complete sentence or thought. Ensure the final sentence is entirely completed to avoid any abrupt cutoff.
- Never split a sentence across clip boundaries. If a sentence spans multiple transcript segments, you must include all of them.
- If the transcript lacks punctuation (auto-generated), infer natural pauses, semantic clauses, or completed phrasings.
- The ending MUST be exceptionally clean: ensure the clip ends on a complete sentence or a finished thought with a natural pause, leaving no trailing words or trailing sentences cut in half.

--- CLIP SELECTION CRITERIA ---
Only select a moment if it satisfies ALL of the following:
1. HOOK (first 3 seconds): The clip starts at a segment boundary where the speaker begins a complete sentence, making a bold claim, asking a surprising question, or dropping a shocking fact. The viewer must be immediately gripped.
2. CORE VALUE: The clip contains one complete, self-contained idea, explanation, story, or revelation. A viewer who has never seen the full video must be able to fully understand and appreciate the clip on its own.
3. NATURAL ENDING: The clip must end at a clean, natural pause, punchline, or complete conclusion. It must NOT cut off mid-word, mid-sentence, or mid-thought. Ensure there is a complete thought or sentence resolution so the ending does not feel abrupt or jarring.
4. INFORMATIONAL DENSITY: Every second of the clip must be meaningful. Do not include long pauses, repetitive filler, or off-topic tangents.

--- CONTENT PRIORITY (rank moments in this order) ---
1. Surprising or counter-intuitive facts/statistics that most people do not know
2. A clear step-by-step explanation of a complex concept broken down simply
3. A personal story or anecdote that illustrates a powerful lesson
4. A bold prediction, controversial opinion, or hot take backed by evidence
5. A turning-point moment where the speaker reveals something unexpected

--- TITLE, REASON & YOUTUBE SHORTS SEO METADATA ---
- Title: Write a punchy, specific, scroll-stopping title (max 8 words). Do NOT use generic titles like "Key Insight" or "Important Moment".
- Reason: Write 1-2 sentences explaining exactly what the viewer will learn or feel, and why this clip is a must-watch on its own.
- Shorts Title: A click-worthy title designed for YouTube Shorts, including relevant emojis and hashtags (e.g., #shorts, #trending).
- Shorts Description: A brief description containing a summary of the clip, a Call to Action (CTA) like subscribing or visiting, and relevant hashtags.
- Shorts Tags: A list of 3-5 search tags/keywords relevant to the clip's content.

Here is the transcript:
---
{transcript}
---

Return ONLY a raw JSON object with a "clips" key. No markdown, no explanations outside the JSON:
{{
  "clips": [
    {{
      "title": "Punchy, specific scroll-stopping title",
      "start_index": 12,
      "end_index": 25,
      "reason": "What the viewer learns and why it is compelling as a standalone clip.",
      "shorts_title": "Click-worthy Shorts Title with #hashtags!",
      "shorts_description": "Summarize the clip here, add a CTA like 'Subscribe for more!' and include #relevant #hashtags.",
      "shorts_tags": ["tag1", "tag2", "tag3"]
    }}
  ]
}}
"""

_REFINEMENT_PROMPT_TEMPLATE = """\
You are an expert video editor. Your job is to refine the boundaries of a candidate video clip to ensure it starts and ends cleanly without cutting off mid-word or mid-sentence, while maintaining a duration between 25 and 58 seconds.

Here is the metadata of the candidate clip:
- Candidate Current Start Index: {candidate_start}
- Candidate Current End Index: {candidate_end}

Below is the transcript snippet surrounding the clip. Each line is formatted as: [index] [start_time - end_time] text
--- Transcript Segment Window ---
{transcript_window}
---

Your task is to review this window and adjust the start_index and end_index to make the clip's beginning and ending clean:
1. HOOK: The start_index should align with the start of a complete sentence or thought (a great hook).
2. CLEAN ENDING: The end_index must align perfectly with the end of a complete sentence, statement, or thought. Do not cut off in the middle of a phrase or sentence. Target clean endings where the speaker finishes their point and there is a natural pause before the next sentence begins.
3. DURATION: The duration of the refined clip (start of start_idx to end of end_idx) MUST remain between 25 and 58 seconds. If adjusting would violate this constraint, stick as close to the boundaries as possible.
4. Keep the adjustment small. Do not change the core topic of the clip.

Return ONLY a raw JSON object:
{{
  "adjusted_start_index": integer,
  "adjusted_end_index": integer,
  "explanation": "Brief reason for the adjustment"
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


def analyze_with_gemini(transcript: str, raw_transcript: list, api_key: str, num_clips: int = 5, ending_safety_margin: float = 0.4) -> list:
    """
    Uses Gemini or OpenAI to identify highlight clips (25-58 s each).

    Pass api_key='mock' (or any key starting with 'mock') to skip the real
    API call and return scaled pre-built sample clips for local testing.
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

    prompt = _ANALYSIS_PROMPT_TEMPLATE.format(transcript=transcript, num_clips=num_clips)
    response_text = ""

    if api_key.startswith("sk-"):
        logger.info("OpenAI key detected — using gpt-4o-mini for transcript analysis.")
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            response_text = response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise RuntimeError(f"OpenAI API request failed: {e}") from e
    else:
        logger.info("Gemini key detected — using gemini-2.5-flash for transcript analysis.")
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            response_text = response.text
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise RuntimeError(f"Gemini API request failed: {e}") from e

    try:
        data = json.loads(response_text.strip())
        candidates = _extract_clips_list(data)
        
        # Apply num_clips constraint before executing refinement to save API quota & time
        candidates = candidates[:num_clips]
        
        refined_candidates = []
        # Execute refinement (Pass 2) in parallel with throttled workers (max_workers=3)
        # to avoid triggering 429 rate limit errors on free tier
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(_refine_single_clip, candidate, raw_transcript, api_key): candidate
                for candidate in candidates
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    refined = future.result()
                    refined_candidates.append(refined)
                except Exception as e:
                    logger.error(f"Thread failed for candidate clip refinement: {e}. Using original.")
                    refined_candidates.append(candidate)
                    
        return _validate_clips(refined_candidates, raw_transcript, ending_safety_margin=ending_safety_margin)
    except Exception as e:
        logger.error(f"Failed to parse AI response: {response_text!r}. Error: {e}")
        raise RuntimeError(
            f"AI returned an invalid response format or failed to generate JSON: {e}"
        ) from e
