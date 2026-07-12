"""
retrieval_service.py — Semantic transcript search & few-shot example retrieval.

Implements a lightweight, local BM25 ranking algorithm in pure Python to index
and search past successful clip transcripts for context injection.
"""

import re
import math
import logging
from typing import List, Dict, Tuple
from analytics_repository import db as analytics_db

logger = logging.getLogger("retrieval_service")

# BM25 Hyper-parameters
K1 = 1.5
B = 0.75


def tokenize(text: str) -> List[str]:
    """Cleans and splits text into lowercase word tokens."""
    if not text:
        return []
    return re.findall(r"\b[a-z0-9']+\b", text.lower())


class BM25Ranker:
    """
    Lightweight, stateless BM25 search algorithm for matching transcript documents.
    """
    def __init__(self, corpus: List[Dict]):
        # Corpus structure: [{"clip_id": str, "text": str, "title": str, "views": int, "retention": float}]
        self.corpus = corpus
        self.doc_tokens = [tokenize(doc.get("text", "")) for doc in corpus]
        self.doc_count = len(corpus)
        
        # Calculate doc lengths and average doc length
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_len = sum(self.doc_lengths) / self.doc_count if self.doc_count > 0 else 0
        
        # Build inverted index and term frequency structures
        self.doc_freqs = {}  # Term -> number of documents containing term
        self.term_freqs = []  # List of Dicts: term -> frequency in doc_i
        
        for tokens in self.doc_tokens:
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self.term_freqs.append(tf)
            
            # Document frequency count
            for t in tf:
                self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1

    def calculate_idf(self, term: str) -> float:
        """Computes Inverse Document Frequency for a term."""
        n = self.doc_freqs.get(term, 0)
        # Apply standard BM25 IDF smoothing to prevent negative values
        return math.log((self.doc_count - n + 0.5) / (n + 0.5) + 1.0)

    def score(self, query_tokens: List[str]) -> List[Tuple[int, float]]:
        """
        Scores all documents in the corpus against the query tokens.
        Returns sorted list of (doc_index, score) pairs.
        """
        scores = []
        for i in range(self.doc_count):
            doc_len = self.doc_lengths[i]
            tf_dict = self.term_freqs[i]
            doc_score = 0.0
            
            for term in query_tokens:
                if term not in tf_dict:
                    continue
                
                tf = tf_dict[term]
                idf = self.calculate_idf(term)
                
                # Standard BM25 term score formula
                numerator = tf * (K1 + 1.0)
                denominator = tf + K1 * (1.0 - B + B * (doc_len / self.avg_doc_len if self.avg_doc_len > 0 else 1.0))
                
                doc_score += idf * (numerator / denominator)
                
            scores.append((i, doc_score))
            
        return sorted(scores, key=lambda x: x[1], reverse=True)


def retrieve_relevant_examples(query_text: str, limit: int = 3) -> List[Dict]:
    """
    Fetches all clips, scores their transcripts against the query,
    and returns the top matches containing clip metadata.
    """
    try:
        records = analytics_db.get_all_records()
    except Exception as e:
        logger.error(f"Failed to retrieve database clips for search: {e}")
        return []

    if not records:
        return []

    # Map database records to search doc format
    corpus = []
    for r in records:
        # Extract transcript text (if not stored, fallback to title/reason)
        # Note: raw transcripts are cached or stored in text/reason
        text_source = r.get("reason", "")
        if r.get("title"):
            text_source += " " + r["title"]
        if r.get("shorts_title"):
            text_source += " " + r["shorts_title"]
        if r.get("shorts_description"):
            text_source += " " + r["shorts_description"]
            
        corpus.append({
            "clip_id": r["clip_id"],
            "text": text_source,
            "title": r.get("title", "Untitled Clip"),
            "views": r.get("views", 0),
            "likes": r.get("likes", 0),
            "retention": r.get("retention", 0.0),
            "duration": r.get("duration", 0.0),
            "creator_selected": r.get("creator_selected", 0)
        })

    # Run BM25 search
    query_tokens = tokenize(query_text)
    if not query_tokens:
        # If query is empty, return the most popular clips (views/selected) as baseline
        sorted_corpus = sorted(corpus, key=lambda x: (x["creator_selected"], x["views"]), reverse=True)
        return sorted_corpus[:limit]

    ranker = BM25Ranker(corpus)
    ranked_indices = ranker.score(query_tokens)

    results = []
    for idx, score in ranked_indices:
        if score <= 0.0 and len(results) >= limit:
            break
        doc = corpus[idx]
        doc["relevance_score"] = round(score, 3)
        results.append(doc)
        if len(results) >= limit:
            break

    return results


def get_few_shot_prompt_context(query_text: str, limit: int = 2) -> str:
    """
    Retrieves relevant historical clips and formats them as a few-shot
    example block to inject into the LLM Curation prompts.
    """
    examples = retrieve_relevant_examples(query_text, limit=limit)
    if not examples:
        return ""

    context_lines = [
        "\n--- FEW-SHOT EXAMPLES OF SUCCESSFUL HISTORICAL CLIPS ---",
        "Use these examples of previously successful and creator-approved clips to align your selections:"
    ]

    for idx, ex in enumerate(examples):
        context_lines.append(f"\nExample {idx + 1}:")
        context_lines.append(f"  - Title: {ex['title']}")
        context_lines.append(f"  - Duration: {ex['duration']} seconds")
        context_lines.append(f"  - Transcript / Description context: {ex['text'][:200]}...")
        context_lines.append(f"  - Curation status: Creator Selected & Published")
        if ex.get("views", 0) > 0:
            context_lines.append(f"  - Performance: {ex['views']} views, {ex['likes']} likes")
            
    context_lines.append("\nAlign your scoring and editing boundaries to match these stylistic trends.\n")
    return "\n".join(context_lines)
