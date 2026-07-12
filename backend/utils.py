"""
utils.py — Shared utility functions for the ClipMind backend.

All functions here are pure, stateless, and importable by any module.
Do NOT import from job_manager, clipper, or analyzer here to avoid circular imports.
"""

import os
import subprocess
import logging
from typing import Optional

logger = logging.getLogger("utils")


# ── String similarity ──────────────────────────────────────────────────────────

def jaccard_similarity(str1: str, str2: str) -> float:
    """
    Computes the Jaccard similarity between two strings based on their word sets.

    Similarity = |intersection| / |union| of lowercased word sets.
    Returns 0.0 if either string is empty.

    Used for:
    - Deduplicating clips with near-identical transcripts.
    - Matching YouTube channel videos to ClipMind database clips by title.
    """
    s1 = set(str1.lower().split())
    s2 = set(str2.lower().split())
    if not s1 or not s2:
        return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))


# ── Cache path helpers ─────────────────────────────────────────────────────────

def get_cache_path(*parts: str) -> str:
    """
    Returns an absolute-relative path under the output/cache directory.

    Examples:
        get_cache_path("IcxZa7HOW1o.mp4")
            → "output/cache/IcxZa7HOW1o.mp4"
        get_cache_path("transcripts", "IcxZa7HOW1o.json")
            → "output/cache/transcripts/IcxZa7HOW1o.json"
        get_cache_path("checkpoints", "abc123_scout.json")
            → "output/cache/checkpoints/abc123_scout.json"
    """
    return os.path.join("output", "cache", *parts)


def ensure_cache_dir(*parts: str) -> str:
    """
    Like get_cache_path() but also calls os.makedirs() so the directory exists.
    Returns the full path.
    """
    path = get_cache_path(*parts)
    # If the last part looks like a filename (has extension), makedirs on the parent.
    if os.path.splitext(parts[-1])[1]:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    else:
        os.makedirs(path, exist_ok=True)
    return path


# ── FFprobe wrapper ────────────────────────────────────────────────────────────

def run_ffprobe(args: list[str], timeout: int = 15) -> str:
    """
    Runs ffprobe with the given arguments and returns stdout as a string.

    The caller should pass everything after the 'ffprobe' binary itself, e.g.:
        run_ffprobe(["-v", "error", "-show_entries", "stream=width", ...])

    Raises:
        subprocess.CalledProcessError  — non-zero exit code
        subprocess.TimeoutExpired      — probe took longer than `timeout` seconds
        FileNotFoundError              — ffprobe not found in PATH
    """
    cmd = ["ffprobe"] + args
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
        timeout=timeout,
    )
    return result.stdout.strip()


# ── JSON repair utilities ──────────────────────────────────────────────────────
# These were previously private helpers buried in analyzer.py. Moving them here
# makes them available to any module (e.g., upload_package.py) without importing
# the heavyweight analyzer module. analyzer.py re-exports them for backwards compat.

def repair_json(text: str) -> str:
    """
    Best-effort repair of malformed JSON returned by LLMs.

    Handles:
    - Truncated responses (appends missing closing brackets/braces)
    - Raw newlines inside string values (escapes them)
    - Trailing commas before closing brackets
    """
    import re
    text = text.strip()
    if not text:
        return ""

    stack = []
    in_string = False
    escape = False
    repaired_chars = []

    for char in text:
        if in_string:
            if escape:
                escape = False
                repaired_chars.append(char)
            elif char == '\\':
                escape = True
                repaired_chars.append(char)
            elif char == '"':
                in_string = False
                repaired_chars.append(char)
            elif char in ('\n', '\r'):
                repaired_chars.append('\\n' if char == '\n' else '\\r')
            else:
                repaired_chars.append(char)
        else:
            if char == '"':
                in_string = True
                repaired_chars.append(char)
            elif char in ('{', '['):
                stack.append(char)
                repaired_chars.append(char)
            elif char == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                repaired_chars.append(char)
            elif char == ']':
                if stack and stack[-1] == '[':
                    stack.pop()
                repaired_chars.append(char)
            else:
                repaired_chars.append(char)

    repaired_text = "".join(repaired_chars)
    repaired_text = re.sub(r',\s*\}', '}', repaired_text)
    repaired_text = re.sub(r',\s*\]', ']', repaired_text)

    if in_string:
        repaired_text += '"'

    while stack:
        top = stack.pop()
        repaired_text += '}' if top == '{' else ']'

    return repaired_text


def extract_json_from_response(text: str) -> str:
    """
    Extracts and repairs a JSON object or array from an LLM response string.

    Tries in order:
    1. Direct parse (already valid JSON)
    2. Markdown code fence extraction (```json ... ```)
    3. First { or [ brace to last matching } or ]
    4. Repair via repair_json()
    """
    import json, re
    text = text.strip()
    if not text:
        return ""

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    match = re.search(r'```(?:json)?\s*([\{\[].*?[\}\]])\s*```', text, re.DOTALL)
    if match:
        extracted = match.group(1).strip()
    else:
        first_brace = -1
        first_char = None
        for idx, char in enumerate(text):
            if char in ('{', '['):
                first_brace = idx
                first_char = char
                break
        if first_brace != -1:
            target_char = '}' if first_char == '{' else ']'
            last_brace = text.rfind(target_char)
            if last_brace != -1 and last_brace > first_brace:
                extracted = text[first_brace:last_brace + 1].strip()
            else:
                extracted = text[first_brace:].strip()
        else:
            extracted = text

    repaired = repair_json(extracted)
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        return repaired
