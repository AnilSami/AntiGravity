"""
Unit tests for the autonomous AI agents (Strategy, Planner, Reflection, and Decision).
"""

import pytest
import shutil
import tempfile
import os
import json
from analytics_repository import SqliteAnalyticsRepository
import personal_ai.strategy.strategist as strategist
import personal_ai.planning.planner as planner
import personal_ai.decision.decider as decider
import personal_ai.reflection.reflector as reflector
import personal_ai.brain.service as brain_service


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_agents.db")
    repo = SqliteAnalyticsRepository(db_path=db_path)
    
    # Swap global database dependencies
    original_brain_db = brain_service.analytics_db
    original_dec_db = decider.analytics_db
    original_ref_db = reflector.analytics_db
    
    import personal_ai.memory.semantic as sem_memory
    original_sem_db = sem_memory.analytics_db
    
    brain_service.analytics_db = repo
    decider.analytics_db = repo
    reflector.analytics_db = repo
    sem_memory.analytics_db = repo
    
    yield repo
    
    brain_service.analytics_db = original_brain_db
    decider.analytics_db = original_dec_db
    reflector.analytics_db = original_ref_db
    sem_memory.analytics_db = original_sem_db
    shutil.rmtree(temp_dir)


def test_strategy_agent_execution(temp_db):
    """Verify Strategy Agent returns viral video analysis."""
    # Seed brain
    brain_service.get_creator_brain("default")
    
    # Run agent in mock mode
    res = strategist.run_strategy_agent("This is a transcript about coding AI assistants.", api_key="mock_key")
    assert "why_viral" in res
    assert "target_audience" in res
    assert "dominant_emotions" in res
    assert res["confidence_score"] == 0.88


def test_planner_agent_execution():
    """Verify Planner Agent generates multiple ranked clip plans."""
    strategy = {
        "hook_style": "surprise",
        "dominant_emotions": ["excitement"],
        "target_audience": "Software developers"
    }
    plans = planner.run_planner_agent("This segment covers visual ffmpeg filters.", strategy, api_key="mock_key")
    
    assert len(plans) == 2
    assert plans[0]["publishing_priority"] == 1
    assert " ffmpeg " in plans[0]["recommended_title"] or "AI Agent" in plans[0]["recommended_title"]


def test_decision_agent_approve(temp_db):
    """Verify Decision Agent approves plans with high estimated virality."""
    brain_service.get_creator_brain("default")
    
    plan = {
        "recommended_title": "Build an AI agent in 5 minutes! #shorts",
        "hook": "Stop writing manual code.",
        "target_audience": "Developers",
        "estimated_virality": 0.85
    }
    
    res = decider.run_decision_agent(plan, api_key="mock_key")
    assert res["decision"] == "generate"
    assert "aligns with niche" in res["explanation"]


def test_decision_agent_reject(temp_db):
    """Verify Decision Agent rejects plans with low estimated virality."""
    brain_service.get_creator_brain("default")
    
    plan = {
        "recommended_title": "Dry technical tutorial",
        "hook": "Today we look at database indexing syntax.",
        "target_audience": "DBAs",
        "estimated_virality": 0.50
    }
    
    res = decider.run_decision_agent(plan, api_key="mock_key")
    assert res["decision"] == "reject"
    assert "does not meet" in res["explanation"]


def test_reflection_agent_correct_prediction(temp_db):
    """Verify Reflection Agent evaluates accuracy and adjusts scorer weights."""
    brain_service.get_creator_brain("default")
    
    # Seed mock prediction
    clip_id = "test_clip_ref"
    conn = temp_db._get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO creator_predictions (clip_id, predicted_score, detailed_predictions, target_audience, reasoning, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (clip_id, 8.0, json.dumps({"retention": 0.8, "virality": 0.8}), "developers", "Strong potential", 123.45))
    finally:
        conn.close()

    # Run reflector with matching high stats
    res = reflector.run_reflection_agent(clip_id, actual_views=8000, actual_retention=0.82, actual_likes=400, api_key="mock_key")
    
    assert res["prediction_error"] == 0.10
    assert "Predicted high initial hook" in res["what_was_correct"]


def test_reflection_agent_underperforming(temp_db):
    """Verify Reflection Agent notes false positive predictions."""
    brain_service.get_creator_brain("default")
    
    clip_id = "underperforming_clip"
    conn = temp_db._get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO creator_predictions (clip_id, predicted_score, detailed_predictions, target_audience, reasoning, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (clip_id, 9.0, json.dumps({"retention": 0.9, "virality": 0.9}), "developers", "Extremely confident", 123.45))
    finally:
        conn.close()

    # Run reflector with very low actual stats
    res = reflector.run_reflection_agent(clip_id, actual_views=500, actual_retention=0.30, actual_likes=10, api_key="mock_key")
    
    # Should flag prediction error
    assert res["prediction_error"] == 0.40


def test_analyze_with_gemini_integration(temp_db):
    """Verify that when PERSONAL_AI_ENABLED=true, analyze_with_gemini runs the autonomous agents pipeline."""
    from analyzer import analyze_with_gemini
    from unittest.mock import MagicMock
    
    os.environ["PERSONAL_AI_ENABLED"] = "true"
    try:
        raw_transcript = [MagicMock(text=f"line {i}", start=i*5.0, duration=5.0) for i in range(50)]
        res = analyze_with_gemini(
            transcript="This is a test transcript for autonomous agents integration testing.",
            raw_transcript=raw_transcript,
            api_key="mock-api-key"
        )
        # Should have run Strategy + Planner + Decision Agent successfully
        assert len(res) == 2
        assert "AI Agent" in res[0]["title"] or "ffmpeg" in res[0]["title"]
        assert res[0]["virality_score"] == 9.0
    finally:
        os.environ.pop("PERSONAL_AI_ENABLED", None)
