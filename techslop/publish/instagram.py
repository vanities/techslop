"""Instagram Reels upload via the Graph API.

Requires:
    - A Facebook Page connected to an Instagram Business or Creator account
    - A long-lived Page access token with instagram_content_publish scope
    - The IG Business account ID

Env vars:
    INSTAGRAM_ACCESS_TOKEN
    INSTAGRAM_PAGE_ID  (the Instagram Business Account ID, NOT the FB page)

Two-step flow per Reels publishing:
    1. POST /{ig_user_id}/media  → returns a creation_id
    2. POST /{ig_user_id}/media_publish  → publishes the container

The video must be hosted at a public HTTPS URL — Graph API does not accept
local file uploads. We upload to a transient host (here: a presigned S3 URL,
or the user can swap in their own). For the experiment, we recommend uploading
to a temporary public bucket; ergonomics are bad but it's a one-time setup.

For now this assumes ``video_url`` is already publicly reachable. If you need
to host it ad-hoc, set INSTAGRAM_PUBLIC_VIDEO_HOST_HOOK to a callable elsewhere
in your stack.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from techslop.config import settings

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"


def _require_creds() -> None:
    if not (settings.instagram_access_token and settings.instagram_page_id):
        raise RuntimeError(
            "Instagram credentials missing. Set INSTAGRAM_ACCESS_TOKEN and "
            "INSTAGRAM_PAGE_ID (the IG Business Account ID) in .env"
        )


def _create_reel_container(video_url: str, caption: str) -> str:
    """Create a Reels media container; returns creation_id."""
    r = httpx.post(
        f"{GRAPH_BASE}/{settings.instagram_page_id}/media",
        params={
            "access_token": settings.instagram_access_token,
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
        },
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()["id"]


def _wait_for_container(creation_id: str, max_wait: float = 300.0, poll: float = 5.0) -> None:
    """Poll the container until status_code is FINISHED, or raise."""
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        r = httpx.get(
            f"{GRAPH_BASE}/{creation_id}",
            params={
                "fields": "status_code",
                "access_token": settings.instagram_access_token,
            },
            timeout=30.0,
        )
        r.raise_for_status()
        status = r.json().get("status_code")
        logger.debug("IG container %s status=%s", creation_id, status)
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Instagram container errored: {r.json()}")
        time.sleep(poll)
    raise TimeoutError(f"Instagram container {creation_id} not ready after {max_wait}s")


def _publish_container(creation_id: str) -> str:
    r = httpx.post(
        f"{GRAPH_BASE}/{settings.instagram_page_id}/media_publish",
        params={
            "creation_id": creation_id,
            "access_token": settings.instagram_access_token,
        },
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()["id"]


def upload_to_instagram(video_path: Path, title: str, video_url: str | None = None) -> str:
    """Publish a Reel.

    Args:
        video_path: Local MP4. Used only for size logging if video_url is provided.
        title: Caption text.
        video_url: Public HTTPS URL the Graph API can fetch the MP4 from.
            If None, uses INSTAGRAM_PUBLIC_VIDEO_URL_TEMPLATE from settings
            with the video filename interpolated in.

    Returns the published media ID.
    """
    _require_creds()

    if video_url is None:
        template = settings.instagram_public_video_url_template
        if not template:
            raise RuntimeError(
                "No public video_url provided and INSTAGRAM_PUBLIC_VIDEO_URL_TEMPLATE not set. "
                "Instagram Graph API requires a public HTTPS URL — host the file (S3/Cloudflare R2/etc) "
                "and pass video_url, or configure the template."
            )
        video_url = template.format(filename=video_path.name)

    logger.info("Instagram: creating Reels container for %s", video_url)
    creation_id = _create_reel_container(video_url=video_url, caption=title)

    logger.info("Instagram: waiting for container %s to finish processing…", creation_id)
    _wait_for_container(creation_id)

    media_id = _publish_container(creation_id)
    logger.info("Instagram: published media_id=%s", media_id)
    return media_id
