"""Reddit ingestion via public RSS feeds."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import feedparser
import httpx

from techslop.config import settings
from techslop.models import Story

logger = logging.getLogger(__name__)
FEED_URL_TEMPLATE = "https://www.reddit.com/r/{subreddit}/.rss"
USER_AGENT = "techslop/0.1 (news aggregator)"


def _parse_feed(subreddit: str) -> list[Story]:
    """Fetch and parse a single subreddit RSS feed into Story objects."""
    url = FEED_URL_TEMPLATE.format(subreddit=subreddit)
    stories: list[Story] = []

    try:
        # Reddit blocks default feedparser UA, so fetch with httpx first
        resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=15, follow_redirects=True)
        resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            logger.warning(
                "feedparser reported an error for r/%s: %s",
                subreddit,
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

            position_score = float(total - rank)

            stories.append(
                Story(
                    id=story_id,
                    title=title,
                    url=link,
                    source="reddit",
                    score=position_score,
                    published_at=published_at,
                    raw_data=dict(entry),
                )
            )

    except Exception as exc:
        logger.error("Reddit ingestion failed for r/%s: %s", subreddit, exc)

    return stories


async def fetch_reddit() -> list[Story]:
    """Fetch stories from all configured subreddit RSS feeds."""
    all_stories: list[Story] = []

    subreddits = [s.strip() for s in settings.reddit_subreddits.split(",")]
    for subreddit in subreddits:
        stories = _parse_feed(subreddit)
        all_stories.extend(stories)
        logger.info("Fetched %d stories from r/%s", len(stories), subreddit)

    logger.info("Fetched %d total stories from Reddit", len(all_stories))
    return all_stories
