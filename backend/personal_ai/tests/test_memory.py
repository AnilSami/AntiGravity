"""
Unit tests for memory sub-package (short-term, long-term, semantic).
"""

import pytest
import shutil
import tempfile
import os
from analytics_repository import SqliteAnalyticsRepository
import personal_ai.memory.short_term as st_memory
import personal_ai.memory.long_term as lt_memory
import personal_ai.memory.semantic as sem_memory

@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_memory.db")
    repo = SqliteAnalyticsRepository(db_path=db_path)
    
    # Swap global database dependencies
    original_lt_db = lt_memory.analytics_db
    original_sem_db = sem_memory.analytics_db
    lt_memory.analytics_db = repo
    sem_memory.analytics_db = repo
    
    yield repo
    
    lt_memory.analytics_db = original_lt_db
    sem_memory.analytics_db = original_sem_db
    shutil.rmtree(temp_dir)


def test_short_term_memory_session():
    """Verify session data is stored and cleared from in-memory cache correctly."""
    st_memory.start_session("vid_123", [{"text": "Hello world"}])
    session = st_memory.get_session("vid_123")
    assert session is not None
    assert len(session["transcript"]) == 1
    
    st_memory.update_session("vid_123", "active_parameters", {"custom_font": "Verdana"})
    assert st_memory.get_session("vid_123")["active_parameters"]["custom_font"] == "Verdana"
    
    st_memory.clear_session("vid_123")
    assert st_memory.get_session("vid_123") is None


def test_long_term_memory_sql(temp_db):
    """Verify long-term entries are saved and fetched from sqlite memory table."""
    mem_id = lt_memory.add_long_term_memory("preferences", "Font color changed to yellow", {"font": "yellow"})
    assert mem_id.startswith("mem_")
    
    mems = lt_memory.get_memories_by_category("preferences", limit=5)
    assert len(mems) == 1
    assert mems[0]["content"] == "Font color changed to yellow"
    assert mems[0]["metadata"]["font"] == "yellow"


def test_semantic_pattern_ranking(temp_db):
    """Verify semantic patterns can be saved and searched using local BM25 ranking."""
    sem_memory.add_successful_pattern("hook", "How to build an AI coding agent", {"views": 12000})
    sem_memory.add_successful_pattern("hook", "Visual effects overlay tutorials in ffmpeg", {"views": 4500})
    
    # Query for "coding agent" -> should rank "How to build an AI coding agent" highest
    matches = sem_memory.query_semantic_patterns("hook", "coding agent", limit=1)
    assert len(matches) == 1
    assert "coding agent" in matches[0]["text"]
