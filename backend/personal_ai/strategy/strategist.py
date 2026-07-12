"""
strategist.py — Pre-clipping strategic analysis of YouTube videos.
"""

import json
import logging
from typing import Dict, Any, Optional
from personal_ai.brain.service import get_creator_brain
from personal_ai.memory.semantic import query_semantic_patterns
from personal_ai.prompts.templates import STRATEGY_AGENT_PROMPT

logger = logging.getLogger("personal_ai.strategy.strategist")


def run_strategy_agent(
    video_text: str,
    api_key: Optional[str] = None,
    brain_id: str = "default"
) -> Dict[str, Any]:
    """
    Runs the Strategy Agent on the video transcript or description.
    References Creator Brain preferences and past successful patterns.
    """
    brain = get_creator_brain(brain_id)
    niche = brain.creator_profile.niche
    tone = brain.creator_profile.tone
    demographics = json.dumps(brain.creator_profile.demographics)

    # Fetch successful patterns for few-shot referencing
    patterns = query_semantic_patterns("hook", video_text, limit=2)
    patterns_text = ""
    for idx, p in enumerate(patterns):
        patterns_text += f"- Successful Pattern {idx+1}: {p.get('text')}\n"

    if not patterns_text:
        patterns_text = "No previous successful patterns found. Define viral strategies from scratch."

    # Build prompt
    prompt = STRATEGY_AGENT_PROMPT.format(
        niche=niche,
        tone=tone,
        demographics=demographics,
        successful_patterns=patterns_text,
        video_text=video_text[:3000]  # Limit context length
    )

    # Mock fallback for unit tests or if mock key is provided
    if not api_key or api_key.startswith("mock"):
        return {
            "why_viral": "The video discusses AI coding agents, which is currently a high-interest trend with high click velocity.",
            "target_audience": "Tech enthusiasts, software engineers, and AI developers.",
            "dominant_emotions": ["curiosity", "excitement"],
            "high_potential_moments": [
                {"time_range": "00:15-00:58", "concept": "Demo of autonomous code editing agents"}
            ],
            "hook_style": "surprise",
            "storytelling_structure": "counter-intuitive claim",
            "confidence_score": 0.88
        }

    try:
        from analyzer import LLMResilienceManager
        llm = LLMResilienceManager(primary_key=api_key)
        response = llm.call(
            system_prompt="You are a strategy assistant that outputs only valid JSON.",
            user_prompt=prompt,
            response_json=True
        )
        # Parse result
        from utils import extract_json_from_response
        data = json.loads(extract_json_from_response(response))
        return data
    except Exception as e:
        logger.error(f"Strategy Agent failed: {e}. Falling back to default strategy.")
        return {
            "why_viral": "High interest topic with high informational density.",
            "target_audience": "General audience.",
            "dominant_emotions": ["curiosity"],
            "high_potential_moments": [{"time_range": "00:00-00:45", "concept": "Intro hook"}],
            "hook_style": "question",
            "storytelling_structure": "problem-solution",
            "confidence_score": 0.70
        }
