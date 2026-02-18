"""Source registry -- run all ingestion sources and return scored results."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

from techslop.models import Story
from techslop.ingest.hackernews import fetch_hackernews
from techslop.ingest.reddit import fetch_reddit
from techslop.ingest.techcrunch import fetch_techcrunch
from techslop.ingest.scorer import score_and_rank

logger = logging.getLogger(__name__)

# Each source is an async callable returning a list of stories.
SourceFetcher = Callable[[], Awaitable[list[Story]]]

SOURCES: list[tuple[str, SourceFetcher]] = [
    ("hackernews", fetch_hackernews),
    ("reddit", fetch_reddit),
    ("techcrunch", fetch_techcrunch),
]


async def _run_source(name: str, fetcher: SourceFetcher) -> list[Story]:
    """Run a single source fetcher, catching and logging any errors."""
    try:
        stories = await fetcher()
        logger.info("Source '%s' returned %d stories", name, len(stories))
        return stories
    except Exception as exc:
        logger.error("Source '%s' failed: %s", name, exc)
        return []


async def ingest_all() -> list[Story]:
    """Run every registered source, collect stories, score, dedup, and sort.

    Sources are executed concurrently.  If any individual source fails the
    remaining sources still contribute their stories.

    Returns a deduplicated list of Story objects sorted by final score
    descending.
    """
    tasks = [_run_source(name, fetcher) for name, fetcher in SOURCES]
    results = await asyncio.gather(*tasks)

    all_stories: list[Story] = []
    for stories in results:
        all_stories.extend(stories)

    logger.info("Collected %d raw stories from %d sources", len(all_stories), len(SOURCES))

    ranked = score_and_rank(all_stories)
    logger.info("Final pipeline produced %d scored stories", len(ranked))
    return ranked
