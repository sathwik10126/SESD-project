"""Lightweight local TF-IDF/cosine similarity for EduLink questions.

This module intentionally avoids external AI APIs. It implements a small,
dependency-free TF-IDF pipeline suitable for a college-scale application.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
STOP_WORDS = {
    "a","an","and","are","as","at","be","but","by","can","could","do","does",
    "for","from","how","i","in","is","it","me","my","of","on","or","our",
    "please","should","the","this","to","was","we","what","when","where",
    "which","who","why","with","would","you","your",
}


def tokenize(text: str) -> list[str]:
    tokens = [t.lower() for t in TOKEN_RE.findall(text or "")]
    return [t for t in tokens if len(t) > 1 and t not in STOP_WORDS]


def _term_frequency(tokens: list[str]) -> dict[str, float]:
    counts = Counter(tokens)
    total = max(len(tokens), 1)
    return {term: count / total for term, count in counts.items()}


def _idf(documents: list[list[str]]) -> dict[str, float]:
    n = max(len(documents), 1)
    document_frequency = Counter()
    for tokens in documents:
        document_frequency.update(set(tokens))
    return {
        term: math.log((1 + n) / (1 + df)) + 1.0
        for term, df in document_frequency.items()
    }


def _tfidf(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = _term_frequency(tokens)
    return {term: value * idf.get(term, 0.0) for term, value in tf.items()}


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    common = left.keys() & right.keys()
    dot = sum(left[k] * right[k] for k in common)
    left_norm = math.sqrt(sum(v * v for v in left.values()))
    right_norm = math.sqrt(sum(v * v for v in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def question_text(title: str, body: str) -> str:
    return f"{title or ''} {body or ''}".strip()


def find_similar_questions(
    title: str,
    body: str,
    candidates: Iterable[object],
    *,
    limit: int = 5,
    suggestion_threshold: float = 0.35,
    duplicate_threshold: float = 0.72,
) -> list[dict]:
    """Return sorted similarity matches.

    Candidate objects must expose `id`, `title`, and `body`.
    """
    candidate_list = list(candidates)
    query_tokens = tokenize(question_text(title, body))

    if not query_tokens or not candidate_list:
        return []

    documents = [
        query_tokens,
        *[
            tokenize(question_text(getattr(q, "title", ""), getattr(q, "body", "")))
            for q in candidate_list
        ],
    ]
    idf = _idf(documents)
    query_vector = _tfidf(query_tokens, idf)

    matches = []
    for question, tokens in zip(candidate_list, documents[1:]):
        score = cosine_similarity(query_vector, _tfidf(tokens, idf))
        if score >= suggestion_threshold:
            matches.append(
                {
                    "id": question.id,
                    "title": question.title,
                    "body": question.body,
                    "category": getattr(question, "category", "General"),
                    "similarity": round(score, 4),
                    "similarity_percent": round(score * 100),
                    "possible_duplicate": score >= duplicate_threshold,
                }
            )

    matches.sort(key=lambda item: item["similarity"], reverse=True)
    return matches[:limit]
