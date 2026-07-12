"""
learning_engine.py — Feedback learning loop for scoring optimization.

Analyzes creator actions (accepts/rejects) and actual YouTube analytics
to dynamically tune the virality scoring weights over time.
"""

import logging
import time
from typing import Dict
from analytics_repository import db as analytics_db
from creator_profile import DEFAULT_PROFILE_VERSION, DEFAULT_VIRALITY_WEIGHTS

logger = logging.getLogger("learning_engine")

# Constraints for weight values to keep scoring balanced
MIN_WEIGHT = 0.10
MAX_WEIGHT = 0.60
LEARNING_RATE = 0.05  # Speed of weight adjustments per feedback action


def adjust_weights_on_creator_action(clip_id: str, selected: bool, rejected: bool, profile_version: str = DEFAULT_PROFILE_VERSION) -> dict:
    """
    Adjusts scoring weights when a creator accepts or rejects a clip candidate.
    
    If selected:
        Pushes weights slightly toward the component categories where this clip scored highest.
    If rejected:
        Pushes weights slightly away from the component categories where this clip scored highest.
    """
    clip = analytics_db.get_clip_by_id(clip_id)
    if not clip:
        logger.warning(f"Clip {clip_id} not found for weight adjustment.")
        return {}

    detailed_scores = clip.get("detailed_scores", {})
    if not detailed_scores:
        logger.warning(f"No detailed scores available for clip {clip_id}.")
        return {}

    profile = analytics_db.get_creator_profile_state(profile_version)
    if not profile:
        from creator_profile import get_creator_profile
        profile = get_creator_profile(profile_version)

    current_weights = profile.get("virality_weights", DEFAULT_VIRALITY_WEIGHTS.copy())

    # Map database detailed scores to virality categories:
    # Detailed scores are expected to contain: hook, retention (story/flow), density, flow (camera/edit)
    # We match them to our weight parameters: hook_weight, retention_weight, density_weight, flow_weight
    cat_scores = {
        "hook_weight": detailed_scores.get("hook", 5.0) / 10.0,
        "retention_weight": detailed_scores.get("retention", 5.0) / 10.0,
        "density_weight": detailed_scores.get("density", 5.0) / 10.0,
        "flow_weight": detailed_scores.get("flow", 5.0) / 10.0,
    }

    # Normalize category scores so they sum to 1.0 (relative importance)
    total_score = sum(cat_scores.values())
    if total_score > 0:
        normalized_scores = {k: v / total_score for k, v in cat_scores.items()}
    else:
        normalized_scores = {k: 0.25 for k in cat_scores}

    # Adjust weights based on action
    multiplier = 1.0 if selected else (-1.0 if rejected else 0.0)
    if multiplier == 0.0:
        return current_weights

    adjusted_weights = {}
    for k, current_val in current_weights.items():
        score_diff = normalized_scores[k] - current_val
        adjustment = LEARNING_RATE * score_diff * multiplier
        new_val = current_val + adjustment
        # Apply boundary constraints
        new_val = max(MIN_WEIGHT, min(MAX_WEIGHT, new_val))
        adjusted_weights[k] = new_val

    # Normalize adjusted weights so they sum exactly to 1.0
    total_weight = sum(adjusted_weights.values())
    for k in adjusted_weights:
        adjusted_weights[k] = round(adjusted_weights[k] / total_weight, 3)

    # Save the updated weights back to the profile
    analytics_db.save_creator_profile_state(
        profile_version=profile_version,
        style_preferences=profile["style_preferences"],
        virality_weights=adjusted_weights
    )

    logger.info(f"Scoring weights updated for profile '{profile_version}': {adjusted_weights}")
    return adjusted_weights


def tune_weights_from_analytics(profile_version: str = DEFAULT_PROFILE_VERSION) -> dict:
    """
    Tunes weights based on Pearson correlation between predicted scoring components
    and actual platform performance (views & retention).
    
    Reinforces categories that exhibit high positive correlation with real audience views.
    """
    profile = analytics_db.get_creator_profile_state(profile_version)
    if not profile:
        from creator_profile import get_creator_profile
        profile = get_creator_profile(profile_version)

    current_weights = profile.get("virality_weights", DEFAULT_VIRALITY_WEIGHTS.copy())

    # Get correlation metrics between detailed scores and views/retention
    try:
        correlation_data = analytics_db.get_correlation_data()
    except Exception as e:
        logger.error(f"Failed to fetch correlation data: {e}")
        return current_weights

    if not correlation_data:
        logger.info("No correlation data available yet. Retaining current weights.")
        return current_weights

    # If correlation calculations demonstrate specific components are highly correlated with success:
    # we shift weights toward them.
    # Correlation list contains: {"metric": "hook", "views_correlation": float, "retention_correlation": float}
    adjusted_weights = current_weights.copy()
    
    category_map = {
        "hook": "hook_weight",
        "retention": "retention_weight",
        "density": "density_weight",
        "flow": "flow_weight"
    }

    shifts = {k: 0.0 for k in current_weights}
    for row in correlation_data:
        metric = row.get("metric")
        weight_key = category_map.get(metric)
        if not weight_key:
            continue

        # Combine correlation values (bias views higher)
        views_corr = row.get("views_correlation", 0.0)
        ret_corr = row.get("retention_correlation", 0.0)
        combined_correlation = (views_corr * 0.7) + (ret_corr * 0.3)

        if combined_correlation > 0.15:
            # Positive correlation -> increase weight
            shifts[weight_key] = LEARNING_RATE * combined_correlation
        elif combined_correlation < -0.15:
            # Negative correlation -> decrease weight
            shifts[weight_key] = LEARNING_RATE * combined_correlation

    # Apply shifts
    for k, val in current_weights.items():
        new_val = val + shifts[k]
        new_val = max(MIN_WEIGHT, min(MAX_WEIGHT, new_val))
        adjusted_weights[k] = new_val

    # Re-normalize weights to sum to 1.0
    total_weight = sum(adjusted_weights.values())
    for k in adjusted_weights:
        adjusted_weights[k] = round(adjusted_weights[k] / total_weight, 3)

    # Save state
    analytics_db.save_creator_profile_state(
        profile_version=profile_version,
        style_preferences=profile["style_preferences"],
        virality_weights=adjusted_weights
    )

    logger.info(f"Analytics tuned weights for profile '{profile_version}': {adjusted_weights}")
    return adjusted_weights
