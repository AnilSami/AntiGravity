"""
long_term.py — SQL-backed persistent long-term memories.
"""

import json
import time
from typing import List, Dict, Optional
from analytics_repository import db as analytics_db


def add_long_term_memory(category: str, content: str, metadata: dict = None) -> str:
    """Adds a persistent log entry to creator_memory table."""
    memory_id = f"mem_{int(time.time() * 1000)}"
    meta_json = json.dumps(metadata) if metadata else "{}"
    
    conn = analytics_db._get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO creator_memory (memory_id, category, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (memory_id, category, content, meta_json, time.time()))
        return memory_id
    finally:
        conn.close()


def get_memories_by_category(category: str, limit: int = 20) -> List[Dict]:
    """Retrieves long-term memories matching a category."""
    conn = analytics_db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM creator_memory
            WHERE category = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (category, limit))
        rows = cursor.fetchall()
        
        results = []
        for r in rows:
            results.append({
                "memory_id": r[0],
                "category": r[1],
                "content": r[2],
                "metadata": json.loads(r[3]),
                "created_at": r[4]
            })
        return results
    finally:
        conn.close()
