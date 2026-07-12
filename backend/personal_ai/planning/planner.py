"""
planner.py — Autonomous video clip planners.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from personal_ai.prompts.templates import PLANNER_AGENT_PROMPT

logger = logging.getLogger("personal_ai.planning.planner")


def run_planner_agent(
    segment_text: str,
    strategy: Dict[str, Any],
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Given a segment and strategy config, plans multiple candidate clips
    and returns a ranked list of plans.
    """
    hook_style = strategy.get("hook_style", "surprise")
    emotions = ",".join(strategy.get("dominant_emotions", ["curiosity"]))
    target_audience = strategy.get("target_audience", "general audience")

    prompt = PLANNER_AGENT_PROMPT.format(
        hook_style=hook_style,
        emotions=emotions,
        target_audience=target_audience,
        segment_text=segment_text[:4000]
    )

    if not api_key or api_key.startswith("mock"):
        # Return mock ranked plans for testing
        return [
            {
                "start_index": 5,
                "end_index": 20,
                "hook": "We built a fully autonomous AI agent that commits code without human reviews.",
                "estimated_retention": 0.85,
                "estimated_virality": 0.90,
                "target_audience": "Software engineers",
                "recommended_title": "AI Agent Commits Production Code! #shorts",
                "subtitle_style": "kinetic",
                "music_recommendation": "electronic",
                "publishing_priority": 1
            },
            {
                "start_index": 25,
                "end_index": 45,
                "hook": "Stop doing manual code reviews in 2026. Here is why.",
                "estimated_retention": 0.76,
                "estimated_virality": 0.81,
                "target_audience": "Tech leads",
                "recommended_title": "Stop Code Reviews in 2026! #shorts",
                "subtitle_style": "classic",
                "music_recommendation": "ambient",
                "publishing_priority": 2
            }
        ]

    try:
        from analyzer import LLMResilienceManager
        llm = LLMResilienceManager(primary_key=api_key)
        response = llm.call(
            system_prompt="You are a video planning assistant that outputs only valid JSON.",
            user_prompt=prompt,
            response_json=True
        )
        from utils import extract_json_from_response
        data = json.loads(extract_json_from_response(response))
        plans = data.get("ranked_plans", [])
        
        # Sort plans by estimated virality * estimated retention descending
        plans.sort(key=lambda x: x.get("estimated_virality", 0.5) * x.get("estimated_retention", 0.5), reverse=True)
        return plans
    except Exception as e:
        logger.error(f"Planner Agent failed: {e}. Returning fallback plan.")
        return [
            {
                "start_index": 0,
                "end_index": 10,
                "hook": "Catchy introductory snippet from video.",
                "estimated_retention": 0.60,
                "estimated_virality": 0.60,
                "target_audience": "General audience",
                "recommended_title": "Amazing Video Climax! #shorts",
                "subtitle_style": "classic",
                "music_recommendation": "ambient",
                "publishing_priority": 1
            }
        ]
