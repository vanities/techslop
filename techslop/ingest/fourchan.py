"""4chan /g/ ingestion via the public JSON API."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone

import httpx

from techslop.config import settings
from techslop.models import Story

logger = logging.getLogger(__name__)

CATALOG_URL = "https://a.4cdn.org/g/catalog.json"
THREAD_URL = "https://a.4cdn.org/g/thread/{no}.json"
BOARD_THREAD_URL = "https://boards.4chan.org/g/thread/{no}"
TOP_N = 20
TOP_REPLIES = 5

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return _HTML_TAG_RE.sub("", text)


def _thread_matches(thread: dict, keywords: list[str]) -> bool:
    """Check whether a thread's subject or comment matches any keyword."""
    subject = _strip_html(thread.get("sub", "")).lower()
    comment = _strip_html(thread.get("com", "")).lower()
    combined = f"{subject} {comment}"

    for kw in keywords:
        if kw in combined:
            return True
    return False


def _make_title(thread: dict) -> str:
    """Derive a title from the thread subject or comment text."""
    subject = _strip_html(thread.get("sub", "")).strip()
    if subject:
        return subject

    comment = _strip_html(thread.get("com", "")).strip()
    return comment[:100] if comment else "(no subject)"


async def _fetch_thread_replies(
    client: httpx.AsyncClient, thread_no: int
) -> list[str]:
    """Fetch the full thread and return the top reply texts (HTML stripped)."""
    try:
        resp = await client.get(THREAD_URL.format(no=thread_no))
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Failed to fetch 4chan thread %s: %s", thread_no, exc)
        return []

    posts = data.get("posts", [])
    # Skip the OP (index 0) and grab the next TOP_REPLIES posts.
    replies: list[str] = []
    for post in posts[1 : TOP_REPLIES + 1]:
        text = _strip_html(post.get("com", "")).strip()
        if text:
            replies.append(text)
    return replies


async def fetch_fourchan() -> list[Story]:
    """Fetch trending threads from /g/ that match configured keywords.

    Returns up to TOP_N Story objects sorted by reply count descending.
    """
    keywords = [kw.strip().lower() for kw in settings.fourchan_keywords.split(",") if kw.strip()]
    if not keywords:
        logger.warning("No 4chan keywords configured; skipping source")
        return []

    stories: list[Story] = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch the catalog (all pages of /g/).
            resp = await client.get(CATALOG_URL)
            resp.raise_for_status()
            catalog: list[dict] = resp.json()

            # Flatten threads from every page and filter by keywords.
            matching: list[dict] = []
            for page in catalog:
                for thread in page.get("threads", []):
                    if _thread_matches(thread, keywords):
                        matching.append(thread)

            # Sort by reply count descending and keep top N.
            matching.sort(key=lambda t: t.get("replies", 0), reverse=True)
            matching = matching[:TOP_N]

            # Build Story objects, fetching top replies for each thread.
            for thread in matching:
                thread_no: int = thread["no"]
                thread_url = BOARD_THREAD_URL.format(no=thread_no)
                story_id = hashlib.sha256(thread_url.encode()).hexdigest()

                published_at = datetime.fromtimestamp(
                    thread.get("time", 0), tz=timezone.utc
                )

                replies = await _fetch_thread_replies(client, thread_no)

                stories.append(
                    Story(
                        id=story_id,
                        title=_make_title(thread),
                        url=thread_url,
                        source="4chan",
                        score=float(thread.get("replies", 0)),
                        published_at=published_at,
                        raw_data={
                            "thread_no": thread_no,
                            "subject": thread.get("sub", ""),
                            "comment": _strip_html(thread.get("com", "")),
                            "replies_count": thread.get("replies", 0),
                            "comments": replies,
                        },
                    )
                )

    except (httpx.HTTPError, ValueError) as exc:
        logger.error("4chan /g/ ingestion failed: %s", exc)

    logger.info("Fetched %d stories from 4chan /g/", len(stories))
    return stories
