"""TechCrunch ingestion via RSS feed."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import feedparser

from techslop.models import Story

logger = logging.getLogger(__name__)

FEED_URL = "https://techcrunch.com/feed/"


async def fetch_techcrunch() -> list[Story]:
    """Fetch the latest stories from the TechCrunch RSS feed.

    Stories are scored by position in the feed (same approach as Reddit)
    since the TechCrunch RSS feed is ordered by recency / editorial
    prominence.
    """
    stories: list[Story] = []

    try:
        feed = feedparser.parse(FEED_URL)
        if feed.bozo and not feed.entries:
            logger.warning(
                "feedparser reported an error for TechCrunch: %s",
                feed.bozo_exception,
            )
            return stories

        total = len(feed.entries)
        for rank, entry in enumerate(feed.entries):
            link = entry.get("link", "")
            title = entry.get("title", "")
            if not link or not title:
                continue

            story_id = hashlib.sha256(link.encode()).hexdigest()

            time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            if time_struct:
                published_at = datetime(*time_struct[:6], tzinfo=timezone.utc)
            else:
                published_at = datetime.now(timezone.utc)

            # Position-based score.
            position_score = float(total - rank)

            stories.append(
                Story(
                    id=story_id,
                    title=title,
                    url=link,
                    source="techcrunch",
                    score=position_score,
                    published_at=published_at,
                    raw_data=dict(entry),
                )
            )

    except Exception as exc:
        logger.error("TechCrunch ingestion failed: %s", exc)

    logger.info("Fetched %d stories from TechCrunch", len(stories))
    return stories
