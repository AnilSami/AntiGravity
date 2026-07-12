"""
decider.py — Autonomous decision-making system before clip creation.
"""

import json
import logging
from typing import Dict, Any, Optional
from personal_ai.brain.service import get_creator_brain
from personal_ai.prompts.templates import DECISION_AGENT_PROMPT
from analytics_repository import db as analytics_db

logger = logging.getLogger("personal_ai.decision.decider")


def run_decision_agent(
    clip_plan: Dict[str, Any],
    api_key: Optional[str] = None,
    brain_id: str = "default"
) -> Dict[str, Any]:
    """
    Evaluates a proposed clip plan against the Creator Brain, lessons learned,
    and past reflections to decide: generate, reject, or modify.
    """
    brain = get_creator_brain(brain_id)
    niche = brain.creator_profile.niche
    tone = brain.creator_profile.tone

    # Retrieve lessons learned from database
    lessons_text = ""
    conn = analytics_db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT concept, description FROM creator_lessons LIMIT 5")
        rows = cursor.fetchall()
        for idx, r in enumerate(rows):
            lessons_text += f"- Lesson {idx+1}: {r[0]} ({r[1]})\n"
    except Exception as e:
        logger.error(f"Failed to fetch lessons: {e}")
    finally:
        conn.close()

    if not lessons_text:
        lessons_text = "No anti-patterns logged yet. Standard quality bars apply."

    # Format decider prompt
    prompt = DECISION_AGENT_PROMPT.format(
        niche=niche,
        tone=tone,
        lessons=lessons_text,
        title=clip_plan.get("recommended_title", "Untitled Clip"),
        hook=clip_plan.get("hook", "No hook specified"),
        target_audience=clip_plan.get("target_audience", "general audience")
    )

    if not api_key or api_key.startswith("mock"):
        # Auto-approve high estimated virality, reject low ones
        est_vir = clip_plan.get("estimated_virality", 0.5)
        if est_vir >= 0.80:
            return {
                "decision": "generate",
                "explanation": f"The clip has a very strong estimated virality of {est_vir} and aligns with niche preferences.",
                "modification_suggestions": ""
            }
        elif est_vir >= 0.70:
            return {
                "decision": "modify",
                "explanation": "Decent potential, but recommend sharpening the title to match high-CTR formats.",
                "modification_suggestions": "Make title more urgent."
            }
        else:
            return {
                "decision": "reject",
                "explanation": f"Clip does not meet the minimum viral threshold ({est_vir}).",
                "modification_suggestions": ""
            }

    try:
        from analyzer import LLMResilienceManager
        llm = LLMResilienceManager(primary_key=api_key)
        response = llm.call(
            system_prompt="You are a quality assurance decider assistant that outputs only valid JSON.",
            user_prompt=prompt,
            response_json=True
        )
        from utils import extract_json_from_response
        data = json.loads(extract_json_from_response(response))
        return data
    except Exception as e:
        logger.error(f"Decision Agent failed: {e}. Falling back to default generation approval.")
        return {
            "decision": "generate",
            "explanation": "Fallback approval to prevent blocking generation.",
            "modification_suggestions": ""
        }
