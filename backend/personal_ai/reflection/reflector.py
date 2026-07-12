"""
reflector.py — Asynchronous analytical feedback loops comparing predictions with actual performance.
"""

import json
import time
import logging
from typing import Dict, Any, Optional
from personal_ai.prompts.templates import REFLECTION_AGENT_PROMPT
from analytics_repository import db as analytics_db
from creator_profile import get_creator_profile, DEFAULT_VIRALITY_WEIGHTS

logger = logging.getLogger("personal_ai.reflection.reflector")


def run_reflection_agent(
    clip_id: str,
    actual_views: int,
    actual_retention: float,
    actual_likes: int,
    api_key: Optional[str] = None,
    profile_version: str = "default"
) -> Dict[str, Any]:
    """
    Compares prediction vs actual performance for a clip, records reflections,
    adds lessons learned, and adjusts scorer weights.
    """
    # Fetch prediction data from sqlite
    predicted_score = 5.0
    detailed_predictions = {}
    
    conn = analytics_db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT predicted_score, detailed_predictions FROM creator_predictions WHERE clip_id = ?", (clip_id,))
        row = cursor.fetchone()
        if row:
            predicted_score = row[0]
            try:
                detailed_predictions = json.loads(row[1])
            except Exception:
                detailed_predictions = {}
    except Exception as e:
        logger.error(f"Failed to fetch prediction record for clip {clip_id}: {e}")
    finally:
        conn.close()

    # Format reflection prompt
    prompt = REFLECTION_AGENT_PROMPT.format(
        predicted_score=predicted_score,
        detailed_predictions=json.dumps(detailed_predictions),
        views=actual_views,
        retention=actual_retention,
        likes=actual_likes
    )

    if not api_key or api_key.startswith("mock"):
        # Synthesize realistic mock reflections
        evaluation = "accurate"
        views_diff = actual_views - int(predicted_score * 1000)
        error_val = 0.10
        if abs(views_diff) > 5000:
            evaluation = "underrated" if views_diff > 0 else "overrated"
            error_val = 0.40
            
        reflection_data = {
            "prediction_error": error_val,
            "what_was_correct": "Predicted high initial hook engagement successfully.",
            "what_failed": "Underestimated viral traction of coding themes.",
            "updated_lessons": [f"Coding topics perform exceptionally well when published on weekends for clip {clip_id}"],
            "confidence_adjustment": 0.05,
            "suggested_weight_updates": {
                "hook_weight": 0.02,
                "retention_weight": -0.01,
                "density_weight": 0.0,
                "flow_weight": -0.01
            }
        }
    else:
        try:
            from analyzer import LLMResilienceManager
            llm = LLMResilienceManager(primary_key=api_key)
            response = llm.call(
                system_prompt="You are an analytical reflection auditor assistant that outputs only valid JSON.",
                user_prompt=prompt,
                response_json=True
            )
            from utils import extract_json_from_response
            reflection_data = json.loads(extract_json_from_response(response))
        except Exception as e:
            logger.error(f"Reflection Agent failed: {e}. Falling back to default mock reflection.")
            reflection_data = {
                "prediction_error": 0.0,
                "what_was_correct": "Balanced predictions.",
                "what_failed": "None.",
                "updated_lessons": [],
                "confidence_adjustment": 0.0,
                "suggested_weight_updates": {}
            }

    # Save to creator_reflections table
    reflection_id = f"ref_{int(time.time() * 1000)}"
    views_diff = actual_views - int(predicted_score * 1000)  # simple scaling comparison
    evaluation = "accurate"
    if abs(views_diff) > 2000:
        evaluation = "underrated" if views_diff > 0 else "overrated"

    conn = analytics_db._get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO creator_reflections (reflection_id, clip_id, views_diff, retention_diff, evaluation, weight_adjustments, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                reflection_id,
                clip_id,
                views_diff,
                actual_retention - detailed_predictions.get("retention", 0.0),
                evaluation,
                json.dumps(reflection_data.get("suggested_weight_updates", {})),
                time.time()
            ))

            # Store updated lessons
            for lesson in reflection_data.get("updated_lessons", []):
                lesson_id = f"les_{int(time.time() * 1000)}"
                cursor.execute("""
                    INSERT INTO creator_lessons (lesson_id, type, concept, description, source_clip_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    lesson_id,
                    "lesson",
                    "Analytics Reflection",
                    lesson,
                    clip_id,
                    time.time()
                ))
    except Exception as db_err:
        logger.error(f"Failed to save reflection to database: {db_err}")
    finally:
        conn.close()

    # Apply weight adjustments to Creator Profile state
    try:
        profile = get_creator_profile(profile_version)
        current_weights = profile.get("virality_weights", DEFAULT_VIRALITY_WEIGHTS.copy())
        suggested = reflection_data.get("suggested_weight_updates", {})
        
        updated = {}
        for k, current_val in current_weights.items():
            shift = suggested.get(k, 0.0)
            # Clip shift to prevent excessive jumping
            shift = max(-0.05, min(0.05, shift))
            new_val = max(0.10, min(0.60, current_val + shift))
            updated[k] = new_val

        # Re-normalize to 1.0
        total = sum(updated.values())
        if total > 0:
            for k in updated:
                updated[k] = round(updated[k] / total, 3)
        else:
            updated = DEFAULT_VIRALITY_WEIGHTS.copy()

        # Save back to database
        analytics_db.save_creator_profile_state(
            profile_version=profile_version,
            style_preferences=profile["style_preferences"],
            virality_weights=updated
        )
        logger.info(f"Reflected and updated scorer weights: {updated}")
    except Exception as w_err:
        logger.error(f"Failed to apply reflected weight updates: {w_err}")

    return reflection_data
