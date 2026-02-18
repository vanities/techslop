"""Integration tests that hit real APIs to validate data structures.

Run with: uv run pytest tests/integration/ -v -s
These are slow and require network access.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from techslop.models import Story


def _validate_story(story: Story):
    """Assert a Story has all required fields populated correctly."""
    assert isinstance(story.id, str) and len(story.id) == 64, f"Bad id: {story.id!r}"
    assert isinstance(story.title, str) and len(story.title) > 0, f"Empty title"
    assert isinstance(story.url, str) and story.url.startswith("http"), f"Bad url: {story.url!r}"
    assert isinstance(story.source, str) and len(story.source) > 0
    assert isinstance(story.score, float)
    assert isinstance(story.published_at, datetime)
    assert isinstance(story.raw_data, dict)
    assert story.status == "new"


@pytest.mark.asyncio
async def test_hackernews_live():
    """Fetch real HN stories and validate structure."""
    from techslop.ingest.hackernews import fetch_hackernews

    stories = await fetch_hackernews()

    assert len(stories) > 0, "No stories fetched from HN"
    print(f"\nHN: fetched {len(stories)} stories")

    for story in stories[:3]:
        _validate_story(story)
        assert story.source == "hackernews"
        print(f"  [{story.score:.0f}] {story.title[:60]}")

        # Verify comments structure
        comments = story.raw_data.get("comments", [])
        print(f"    comments: {len(comments)}")
        for c in comments[:2]:
            assert isinstance(c, dict)
            assert "author" in c
            assert "text" in c
            print(f"      [{c['author']}]: {c['text'][:80]}")


@pytest.mark.asyncio
async def test_reddit_live():
    """Fetch real Reddit stories and validate structure."""
    from techslop.ingest.reddit import fetch_reddit

    stories = await fetch_reddit()

    assert len(stories) > 0, "No stories fetched from Reddit"
    print(f"\nReddit: fetched {len(stories)} stories")

    for story in stories[:3]:
        _validate_story(story)
        assert story.source == "reddit"
        print(f"  [{story.score:.0f}] {story.title[:60]}")


@pytest.mark.asyncio
async def test_techcrunch_live():
    """Fetch real TechCrunch stories and validate structure."""
    from techslop.ingest.techcrunch import fetch_techcrunch

    stories = await fetch_techcrunch()

    assert len(stories) > 0, "No stories fetched from TechCrunch"
    print(f"\nTechCrunch: fetched {len(stories)} stories")

    for story in stories[:3]:
        _validate_story(story)
        assert story.source == "techcrunch"
        print(f"  [{story.score:.0f}] {story.title[:60]}")


@pytest.mark.asyncio
async def test_fourchan_live():
    """Fetch real 4chan /g/ threads and validate structure."""
    from techslop.ingest.fourchan import fetch_fourchan

    stories = await fetch_fourchan()

    # May be 0 if no threads match keywords, but shouldn't error
    print(f"\n4chan: fetched {len(stories)} stories")

    for story in stories[:3]:
        _validate_story(story)
        assert story.source == "4chan"
        assert "boards.4chan.org/g/thread" in story.url
        print(f"  [{story.score:.0f}] {story.title[:60]}")

        comments = story.raw_data.get("comments", [])
        print(f"    comments: {len(comments)}")
        for c in comments[:2]:
            assert isinstance(c, str)
            print(f"      {c[:80]}")


@pytest.mark.asyncio
async def test_xtwitter_live():
    """Attempt X/Twitter fetch — expected to fail gracefully if Nitter is down."""
    from techslop.ingest.xtwitter import fetch_x

    stories = await fetch_x()

    # Nitter is often down, so 0 results is fine
    print(f"\nX/Twitter: fetched {len(stories)} stories")

    for story in stories[:3]:
        _validate_story(story)
        assert story.source == "x"
        print(f"  [{story.score:.0f}] {story.title[:60]}")


@pytest.mark.asyncio
async def test_full_ingest_pipeline():
    """Run the full ingestion pipeline and validate scored results."""
    from techslop.ingest.sources import ingest_all

    stories = await ingest_all()

    assert len(stories) > 0, "Full pipeline returned no stories"
    print(f"\nFull pipeline: {len(stories)} stories after scoring/dedup")

    # Should be sorted by score descending
    for i in range(min(len(stories) - 1, 5)):
        assert stories[i].score >= stories[i + 1].score, "Not sorted by score"

    # Print top 10
    print("\nTop 10:")
    for story in stories[:10]:
        _validate_story(story)
        comments = len(story.raw_data.get("comments", []))
        ctx = f" +{comments}c" if comments else ""
        print(f"  {story.score:.3f}  [{story.source:<12}] {story.title[:55]}{ctx}")
