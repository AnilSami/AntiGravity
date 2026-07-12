"""
Unit tests for the Semantic Retrieval Engine (retrieval_service.py).
"""

import pytest
import shutil
import tempfile
import os
from analytics_repository import SqliteAnalyticsRepository
import retrieval_service

@pytest.fixture
def temp_db():
    """Create a temporary sqlite database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_analytics.db")
    
    # Instantiate clean repository
    repo = SqliteAnalyticsRepository(db_path=db_path)
    
    # Swap instances
    original_db = retrieval_service.analytics_db
    retrieval_service.analytics_db = repo
    
    yield repo
    
    # Restore
    retrieval_service.analytics_db = original_db
    shutil.rmtree(temp_dir)


def test_tokenize():
    """Verify tokenize helper cleans text correctly."""
    text = "Hello, World! This is a test... with numbers 1234."
    tokens = retrieval_service.tokenize(text)
    assert tokens == ["hello", "world", "this", "is", "a", "test", "with", "numbers", "1234"]


def test_bm25_ranking_matches():
    """Verify BM25 ranker correctly scores documents based on query terms."""
    corpus = [
        {"clip_id": "c1", "text": "artificial intelligence and machine learning algorithms"},
        {"clip_id": "c2", "text": "video processing ffmpeg overlay filters sound effects"},
        {"clip_id": "c3", "text": "artificial intelligence"}
    ]
    
    ranker = retrieval_service.BM25Ranker(corpus)
    
    # Query: "artificial intelligence" -> matches c1 and c3, c3 has shorter doc length so should score higher
    scores = ranker.score(["artificial", "intelligence"])
    
    assert len(scores) == 3
    # First match should be either c3 or c1 (since they both contain artificial intelligence)
    top_doc = corpus[scores[0][0]]
    assert top_doc["clip_id"] in ["c3", "c1"]
    # c3 is shorter, so it should have a higher score
    assert scores[0][1] > scores[1][1]


def test_retrieve_relevant_examples(temp_db):
    """Verify retrieval returns relevant clips from sqlite database."""
    # Seed clips
    temp_db.save_clip_metadata(
        video_id="vid1",
        clip_id="clipA",
        virality_score=9.0,
        detailed_scores={},
        title="Deep Learning and AI Curation",
        reason="We talk about machine learning models and deep artificial neural networks."
    )
    temp_db.save_clip_metadata(
        video_id="vid1",
        clip_id="clipB",
        virality_score=8.0,
        detailed_scores={},
        title="FFmpeg Video Processing Rendering",
        reason="We talk about filters, keying overlay animations, and video codecs."
    )

    # Search for "neural networks" -> should match clipA
    results = retrieval_service.retrieve_relevant_examples("neural networks", limit=1)
    assert len(results) == 1
    assert results[0]["clip_id"] == "clipA"


def test_get_few_shot_prompt_context(temp_db):
    """Verify few-shot context is formatted correctly into text prompt."""
    temp_db.save_clip_metadata(
        video_id="vid1",
        clip_id="clipA",
        virality_score=9.0,
        detailed_scores={},
        title="Deep Learning and AI Curation",
        reason="We talk about machine learning models."
    )

    context = retrieval_service.get_few_shot_prompt_context("learning models")
    assert "FEW-SHOT EXAMPLES" in context
    assert "Deep Learning and AI Curation" in context
    assert "Curation status:" in context
