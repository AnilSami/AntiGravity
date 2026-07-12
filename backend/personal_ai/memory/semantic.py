"""
semantic.py — Semantic indexing and matching of successful/failed patterns.
"""

import json
import time
from typing import List, Dict
from analytics_repository import db as analytics_db
from retrieval_service import tokenize, BM25Ranker


def add_successful_pattern(pattern_type: str, text_content: str, success_metrics: dict):
    """Saves a positive clip pattern to sqlite memory."""
    pattern_id = f"pattern_s_{int(time.time() * 1000)}"
    conn = analytics_db._get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO successful_patterns (pattern_id, pattern_type, text_content, success_metrics, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (pattern_id, pattern_type, text_content, json.dumps(success_metrics), time.time()))
    finally:
        conn.close()


def add_failed_pattern(pattern_type: str, text_content: str, fail_reason: str):
    """Saves a negative clip pattern (mistake) to sqlite memory."""
    pattern_id = f"pattern_f_{int(time.time() * 1000)}"
    conn = analytics_db._get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO failed_patterns (pattern_id, pattern_type, text_content, fail_reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (pattern_id, pattern_type, text_content, fail_reason, time.time()))
    finally:
        conn.close()


def query_semantic_patterns(pattern_type: str, query_text: str, limit: int = 3) -> List[Dict]:
    """
    Queries successful patterns matching the query_text using BM25 token relevance.
    """
    conn = analytics_db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pattern_id, text_content, success_metrics FROM successful_patterns
            WHERE pattern_type = ?
        """, (pattern_type,))
        rows = cursor.fetchall()
        
        if not rows:
            return []
            
        corpus = []
        for r in rows:
            corpus.append({
                "pattern_id": r[0],
                "text": r[1],
                "metrics": json.loads(r[2])
            })
            
        query_tokens = tokenize(query_text)
        if not query_tokens:
            return corpus[:limit]
            
        ranker = BM25Ranker(corpus)
        scores = ranker.score(query_tokens)
        
        results = []
        for idx, score in scores:
            if len(results) >= limit:
                break
            doc = corpus[idx]
            doc["relevance_score"] = round(score, 3)
            results.append(doc)
        return results
    finally:
        conn.close()
