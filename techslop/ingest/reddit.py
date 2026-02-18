"""Reddit ingestion via public RSS feeds."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import feedparser

from techslop.models import Story

logger = logging.getLogger(__name__)

SUBREDDITS = ["technology", "programming"]
FEED_URL_TEMPLATE = "https://www.reddit.com/r/{subreddit}/.rss"


def _parse_feed(subreddit: str) -> list[Story]:
    """Parse a single subreddit RSS feed into Story objects.

    Stories are scored by their position in the feed: the first entry gets
    the highest score (equal to total number of entries) and the last entry
    gets a score of 1.  This reflects Reddit's default "hot" ranking.
    """
    url = FEED_URL_TEMPLATE.format(subreddit=subreddit)
    stories: list[Story] = []

    try:
        feed = feedparser.parse(url)
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

            # Prefer the published timestamp; fall back to updated, then now.
            time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            if time_struct:
                published_at = datetime(*time_struct[:6], tzinfo=timezone.utc)
            else:
                published_at = datetime.now(timezone.utc)

            # Position-based score: top of feed = highest score.
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
    """Fetch stories from all configured subreddit RSS feeds.

    feedparser is synchronous, but we wrap the call in an async function
    so it conforms to the same interface as the other source fetchers.
    """
    all_stories: list[Story] = []

    for subreddit in SUBREDDITS:
        stories = _parse_feed(subreddit)
        all_stories.extend(stories)
        logger.info("Fetched %d stories from r/%s", len(stories), subreddit)

    logger.info("Fetched %d total stories from Reddit", len(all_stories))
    return all_stories
