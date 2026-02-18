"""X/Twitter ingestion via Nitter RSS feeds."""

from __future__ import annotations

import hashlib
import logging
import urllib.parse
from datetime import datetime, timezone

import feedparser
import httpx

from techslop.config import settings
from techslop.models import Story

logger = logging.getLogger(__name__)

NITTER_SEARCH_RSS = "https://nitter.net/search/rss?f=tweets&q={query}"


def _parse_feed_entries(feed: feedparser.FeedParserDict) -> list[Story]:
    """Convert parsed RSS entries into Story objects.

    Stories are scored by position in the feed (first = highest) to
    approximate relevance/recency ranking.
    """
    stories: list[Story] = []
    total = len(feed.entries)

    for rank, entry in enumerate(feed.entries):
        link = entry.get("link", "")
        title = entry.get("title", "")
        if not link:
            continue

        story_id = hashlib.sha256(link.encode()).hexdigest()

        # Prefer the published timestamp; fall back to now.
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if time_struct:
            published_at = datetime(*time_struct[:6], tzinfo=timezone.utc)
        else:
            published_at = datetime.now(timezone.utc)

        # Position-based score: top of feed = highest.
        position_score = float(total - rank)

        tweet_text = entry.get("summary", title)

        stories.append(
            Story(
                id=story_id,
                title=title[:200] if title else link,
                url=link,
                source="x",
                score=position_score,
                published_at=published_at,
                raw_data={
                    "tweet_text": tweet_text,
                    "entry": dict(entry),
                },
            )
        )

    return stories


async def fetch_x() -> list[Story]:
    """Fetch tweets matching configured keywords via Nitter RSS.

    Each keyword triggers a separate search-RSS request.  Results are
    deduplicated by story id across all keyword searches.  All network and
    parsing failures are caught so this source never crashes the pipeline.
    """
    keywords = [kw.strip() for kw in settings.x_keywords.split(",") if kw.strip()]
    if not keywords:
        logger.warning("No X/Twitter keywords configured; skipping source")
        return []

    seen_ids: set[str] = set()
    all_stories: list[Story] = []

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for keyword in keywords:
                try:
                    encoded_query = urllib.parse.quote_plus(keyword)
                    url = NITTER_SEARCH_RSS.format(query=encoded_query)

                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning(
                            "Nitter returned status %d for keyword '%s'; skipping",
                            resp.status_code,
                            keyword,
                        )
                        continue

                    feed = feedparser.parse(resp.text)
                    if feed.bozo and not feed.entries:
                        logger.warning(
                            "feedparser error for X keyword '%s': %s",
                            keyword,
                            feed.bozo_exception,
                        )
                        continue

                    stories = _parse_feed_entries(feed)
                    for story in stories:
                        if story.id not in seen_ids:
                            seen_ids.add(story.id)
                            all_stories.append(story)

                    logger.debug(
                        "Keyword '%s' yielded %d tweets (%d new)",
                        keyword,
                        len(stories),
                        sum(1 for s in stories if s.id in seen_ids),
                    )

                except (httpx.HTTPError, httpx.ConnectError) as exc:
                    logger.warning(
                        "Nitter request failed for keyword '%s': %s", keyword, exc
                    )
                    continue
                except Exception as exc:
                    logger.warning(
                        "Unexpected error fetching X keyword '%s': %s", keyword, exc
                    )
                    continue

    except (httpx.HTTPError, httpx.ConnectError) as exc:
        logger.warning("Could not connect to Nitter at all: %s", exc)
    except Exception as exc:
        logger.error("X/Twitter ingestion failed unexpectedly: %s", exc)

    logger.info("Fetched %d stories from X/Twitter (Nitter)", len(all_stories))
    return all_stories
