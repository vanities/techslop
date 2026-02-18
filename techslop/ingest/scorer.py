"""Score, rank, and deduplicate ingested stories."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from techslop.models import Story

logger = logging.getLogger(__name__)

# Per-source quality weights.
SOURCE_WEIGHTS: dict[str, float] = {
    "hackernews": 1.0,
    "techcrunch": 0.9,
    "x": 0.85,
    "reddit": 0.8,
    "4chan": 0.7,
}

# Stories published less than this many hours ago get a recency boost.
RECENCY_HOURS = 6
RECENCY_BOOST = 0.15


def _normalize_scores(stories: list[Story]) -> None:
    """Normalize raw scores to [0, 1] within each source, in place."""
    sources: dict[str, list[Story]] = {}
    for story in stories:
        sources.setdefault(story.source, []).append(story)

    for source, group in sources.items():
        scores = [s.score for s in group]
        min_score = min(scores)
        max_score = max(scores)
        span = max_score - min_score

        if span == 0:
            # All scores identical -- assign 1.0 to every story.
            for s in group:
                s.score = 1.0
        else:
            for s in group:
                s.score = (s.score - min_score) / span


def _apply_source_weights(stories: list[Story]) -> None:
    """Multiply each story's normalized score by its source weight."""
    for story in stories:
        weight = SOURCE_WEIGHTS.get(story.source, 0.5)
        story.score *= weight


def _apply_recency_boost(stories: list[Story]) -> None:
    """Give a boost to stories published within RECENCY_HOURS."""
    now = datetime.now(timezone.utc)
    for story in stories:
        age_hours = (now - story.published_at).total_seconds() / 3600
        if age_hours < RECENCY_HOURS:
            story.score += RECENCY_BOOST


def deduplicate(stories: list[Story]) -> list[Story]:
    """Remove duplicate stories based on their id (SHA-256 of URL).

    When duplicates exist, the copy with the highest score is kept.
    """
    best: dict[str, Story] = {}
    for story in stories:
        existing = best.get(story.id)
        if existing is None or story.score > existing.score:
            best[story.id] = story

    deduped = list(best.values())
    removed = len(stories) - len(deduped)
    if removed:
        logger.info("Removed %d duplicate stories", removed)
    return deduped


def score_and_rank(stories: list[Story]) -> list[Story]:
    """Full scoring pipeline: normalize, weight, boost, dedup, sort.

    Returns a new list sorted by final score descending.
    """
    if not stories:
        return []

    _normalize_scores(stories)
    _apply_source_weights(stories)
    _apply_recency_boost(stories)

    unique = deduplicate(stories)
    unique.sort(key=lambda s: s.score, reverse=True)

    logger.info(
        "Scored and ranked %d stories (top score: %.3f)",
        len(unique),
        unique[0].score if unique else 0,
    )
    return unique
