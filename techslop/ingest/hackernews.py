"""Hacker News ingestion via the Firebase API."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import httpx

from techslop.models import Story

logger = logging.getLogger(__name__)

HN_BASE = "https://hacker-news.firebaseio.com/v0"
TOP_N = 30


async def _fetch_item(client: httpx.AsyncClient, item_id: int) -> dict | None:
    """Fetch a single HN item by ID, returning None on failure."""
    try:
        resp = await client.get(f"{HN_BASE}/item/{item_id}.json")
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Failed to fetch HN item %s: %s", item_id, exc)
        return None


def _make_story(item: dict) -> Story | None:
    """Convert an HN item dict into a Story, or None if unusable."""
    url = item.get("url")
    if not url:
        # Self-posts link to the HN comments page instead.
        url = f"https://news.ycombinator.com/item?id={item['id']}"

    title = item.get("title", "")
    if not title:
        return None

    story_id = hashlib.sha256(url.encode()).hexdigest()
    published_at = datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc)

    return Story(
        id=story_id,
        title=title,
        url=url,
        source="hackernews",
        score=float(item.get("score", 0)),
        published_at=published_at,
        raw_data=item,
    )


async def fetch_hackernews() -> list[Story]:
    """Fetch the current top stories from Hacker News.

    Returns up to TOP_N Story objects sorted by HN score descending.
    """
    stories: list[Story] = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{HN_BASE}/topstories.json")
            resp.raise_for_status()
            top_ids: list[int] = resp.json()[:TOP_N]

            for item_id in top_ids:
                item = await _fetch_item(client, item_id)
                if item is None:
                    continue
                story = _make_story(item)
                if story is not None:
                    stories.append(story)

    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Hacker News ingestion failed: %s", exc)

    logger.info("Fetched %d stories from Hacker News", len(stories))
    return stories
