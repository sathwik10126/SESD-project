"""Helpful-answer ranking for EduLink."""

from __future__ import annotations

import math
from datetime import datetime, timezone


def answer_rank_score(
    *,
    helpful_votes: int,
    faculty_verified: bool,
    created_at: datetime | None,
    now: datetime | None = None,
) -> float:
    """Calculate a transparent answer score.

    Formula:
      helpful component = 2 points per helpful vote
      faculty verification = +3 points
      recency = up to +1 point, decaying exponentially over 30 days

    The formula is deliberately simple and explainable for the project.
    """
    now = now or datetime.now(timezone.utc)
    age_days = 0.0
    if created_at:
        created = created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = max((now - created).total_seconds() / 86400.0, 0.0)

    recency = math.exp(-age_days / 30.0)
    return round(
        (max(helpful_votes, 0) * 2.0)
        + (3.0 if faculty_verified else 0.0)
        + recency,
        6,
    )
