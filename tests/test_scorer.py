"""Tests for techslop.ingest.scorer."""

from datetime import datetime, timedelta, timezone

from techslop.ingest.scorer import deduplicate, score_and_rank
from techslop.models import Story


def _story(id: str, source: str = "hackernews", score: float = 10.0, hours_ago: float = 1.0) -> Story:
    return Story(
        id=id,
        title=f"Story {id}",
        url=f"https://example.com/{id}",
        source=source,
        score=score,
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )


def test_dedup_keeps_highest_score():
    stories = [
        _story("a", score=10.0),
        _story("a", score=20.0),
        _story("b", score=5.0),
    ]
    result = deduplicate(stories)
    assert len(result) == 2
    a = next(s for s in result if s.id == "a")
    assert a.score == 20.0


def test_score_and_rank_empty():
    assert score_and_rank([]) == []


def test_score_and_rank_sorts_descending():
    stories = [
        _story("a", score=5.0),
        _story("b", score=50.0),
        _story("c", score=25.0),
    ]
    ranked = score_and_rank(stories)
    assert ranked[0].score >= ranked[1].score >= ranked[2].score


def test_source_weights_affect_ranking():
    # HN (weight 1.0) should rank higher than 4chan (weight 0.7) at same raw score
    stories = [
        _story("hn", source="hackernews", score=100.0),
        _story("4c", source="4chan", score=100.0),
    ]
    ranked = score_and_rank(stories)
    hn = next(s for s in ranked if s.source == "hackernews")
    fc = next(s for s in ranked if s.source == "4chan")
    assert hn.score > fc.score


def test_recency_boost():
    stories = [
        _story("recent", score=10.0, hours_ago=1.0),  # within 6 hours
        _story("old", score=10.0, hours_ago=24.0),     # outside 6 hours
    ]
    ranked = score_and_rank(stories)
    recent = next(s for s in ranked if s.id == "recent")
    old = next(s for s in ranked if s.id == "old")
    assert recent.score > old.score
