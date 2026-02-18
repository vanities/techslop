"""Tests for ingestion sources with mocked HTTP."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_hackernews_fetch():
    """HN fetcher should create Stories from API responses."""
    mock_topstories = list(range(1, 4))  # 3 story IDs
    mock_items = {
        1: {"id": 1, "title": "Story 1", "url": "https://a.com", "score": 100, "time": 1700000000, "kids": [10, 11]},
        2: {"id": 2, "title": "Story 2", "url": "https://b.com", "score": 50, "time": 1700000000, "kids": []},
        3: {"id": 3, "title": "Story 3", "url": "https://c.com", "score": 75, "time": 1700000000, "kids": [12]},
        10: {"id": 10, "by": "user1", "text": "Great article!", "type": "comment"},
        11: {"id": 11, "by": "user2", "text": "Interesting take.", "type": "comment"},
        12: {"id": 12, "by": "user3", "text": "<p>HTML comment</p>", "type": "comment"},
    }

    class MockResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._data

    class MockClient:
        async def get(self, url):
            if "topstories" in url:
                return MockResponse(mock_topstories)
            # Extract item ID from URL like ".../item/12.json"
            item_id = int(url.split("/item/")[1].replace(".json", ""))
            if item_id in mock_items:
                return MockResponse(mock_items[item_id])
            return MockResponse(None)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    with patch("techslop.ingest.hackernews.httpx.AsyncClient", return_value=MockClient()):
        from techslop.ingest.hackernews import fetch_hackernews
        stories = await fetch_hackernews()

    assert len(stories) == 3
    # Check that comments were fetched
    story1 = next(s for s in stories if s.title == "Story 1")
    assert "comments" in story1.raw_data
    assert len(story1.raw_data["comments"]) == 2


@pytest.mark.asyncio
async def test_reddit_fetch():
    """Reddit fetcher should parse RSS entries."""
    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [
        {"link": "https://reddit.com/1", "title": "Post 1", "published_parsed": (2024, 1, 1, 0, 0, 0, 0, 0, 0)},
        {"link": "https://reddit.com/2", "title": "Post 2", "published_parsed": (2024, 1, 1, 0, 0, 0, 0, 0, 0)},
    ]

    with patch("techslop.ingest.reddit.feedparser.parse", return_value=mock_feed):
        with patch("techslop.ingest.reddit.settings") as mock_settings:
            mock_settings.reddit_subreddits = "technology"
            from techslop.ingest.reddit import fetch_reddit
            stories = await fetch_reddit()

    assert len(stories) == 2
    assert all(s.source == "reddit" for s in stories)


@pytest.mark.asyncio
async def test_fourchan_fetch():
    """4chan fetcher should filter by keywords."""
    catalog = [
        {"threads": [
            {"no": 1, "sub": "AI thread", "com": "Talking about LLMs", "time": 1700000000, "replies": 50},
            {"no": 2, "sub": "Anime thread", "com": "Off topic", "time": 1700000000, "replies": 100},
            {"no": 3, "com": "Python is great for GPU computing", "time": 1700000000, "replies": 30},
        ]}
    ]
    thread_1 = {"posts": [
        {"no": 1, "sub": "AI thread", "com": "OP"},
        {"no": 10, "com": "Reply 1"},
        {"no": 11, "com": "Reply 2"},
    ]}
    thread_3 = {"posts": [
        {"no": 3, "com": "Python is great for GPU computing"},
        {"no": 20, "com": "Agree!"},
    ]}

    class MockResponse:
        status_code = 200
        def __init__(self, data):
            self._data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self._data

    class MockClient:
        async def get(self, url):
            if "catalog" in url:
                return MockResponse(catalog)
            if "thread/1" in url:
                return MockResponse(thread_1)
            if "thread/3" in url:
                return MockResponse(thread_3)
            return MockResponse({"posts": []})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    with patch("techslop.ingest.fourchan.httpx.AsyncClient", return_value=MockClient()):
        with patch("techslop.ingest.fourchan.settings") as mock_settings:
            mock_settings.fourchan_keywords = "AI,LLM,GPU,python"
            from techslop.ingest.fourchan import fetch_fourchan
            stories = await fetch_fourchan()

    # Should match thread 1 (AI, LLMs) and thread 3 (Python, GPU), NOT thread 2 (anime)
    assert len(stories) == 2
    assert all(s.source == "4chan" for s in stories)
