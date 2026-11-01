from datetime import datetime, timedelta, timezone

from app.services.answer_ranking import answer_rank_score
from app.services.question_similarity import (
    cosine_similarity,
    find_similar_questions,
    tokenize,
)


class Q:
    def __init__(self, id, title, body, category="General"):
        self.id = id
        self.title = title
        self.body = body
        self.category = category


def test_tokenizer_and_cosine():
    assert "certificate" in tokenize("How do I get a certificate?")
    assert cosine_similarity({"a": 1.0}, {"a": 1.0}) == 1.0
    assert cosine_similarity({}, {"a": 1.0}) == 0.0


def test_similar_question_detection():
    candidates = [
        Q(1, "How can I get a bonafide certificate?", "I need it for an internship."),
        Q(2, "Best way to learn graph algorithms", "I want resources for BFS and DFS."),
    ]

    matches = find_similar_questions(
        "How do I apply for a bonafide certificate?",
        "I need a bonafide for my internship.",
        candidates,
        suggestion_threshold=0.2,
        duplicate_threshold=0.7,
    )

    assert matches
    assert matches[0]["id"] == 1
    assert matches[0]["similarity"] > 0


def test_unrelated_question_is_not_a_match():
    candidates = [
        Q(1, "How can I get a bonafide certificate?", "Internship document"),
    ]

    matches = find_similar_questions(
        "How do I fix a binary search tree?",
        "My AVL tree rotation is failing.",
        candidates,
        suggestion_threshold=0.5,
    )

    assert matches == []


def test_answer_ranking_signals():
    now = datetime.now(timezone.utc)
    helpful = answer_rank_score(
        helpful_votes=2,
        faculty_verified=False,
        created_at=now,
        now=now,
    )
    verified = answer_rank_score(
        helpful_votes=0,
        faculty_verified=True,
        created_at=now,
        now=now,
    )
    assert helpful > 0
    assert verified > 0

    old = answer_rank_score(
        helpful_votes=0,
        faculty_verified=False,
        created_at=now - timedelta(days=60),
        now=now,
    )
    fresh = answer_rank_score(
        helpful_votes=0,
        faculty_verified=False,
        created_at=now,
        now=now,
    )
    assert fresh > old
