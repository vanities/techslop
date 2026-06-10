"""TikTok upload via the Content Posting API.

Requires a TikTok Developer app with Content Posting API scope and an OAuth
refresh token for the target account. See:
https://developers.tiktok.com/doc/content-posting-api-get-started

Env vars:
    TIKTOK_CLIENT_KEY
    TIKTOK_CLIENT_SECRET
    TIKTOK_REFRESH_TOKEN

Two-step flow:
    1. POST /v2/post/publish/inbox/video/init/  → upload URL + publish_id
    2. PUT the binary to the upload URL
    3. (TikTok finalizes async; the video lands in the user's "drafts" inbox
       on mobile until they tap "post". This is the safest mode for indie
       devs — it requires audited "direct post" approval from TikTok to
       skip the inbox.)
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from techslop.config import settings

logger = logging.getLogger(__name__)

OAUTH_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"


def _refresh_access_token() -> str:
    """Exchange the long-lived refresh_token for a short-lived access_token."""
    if not (settings.tiktok_client_key and settings.tiktok_client_secret and settings.tiktok_refresh_token):
        raise RuntimeError(
            "TikTok credentials missing. Set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, "
            "TIKTOK_REFRESH_TOKEN in .env"
        )

    r = httpx.post(
        OAUTH_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": settings.tiktok_refresh_token,
        },
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def upload_to_tiktok(video_path: Path, title: str) -> str:
    """Upload a video to the authenticated TikTok account's drafts inbox.

    Returns the publish_id assigned by TikTok. The video lands in the user's
    mobile drafts; final posting requires a tap unless the app has been
    granted "direct post" by TikTok review.
    """
    access_token = _refresh_access_token()
    video_size = video_path.stat().st_size

    init_payload = {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,
            "total_chunk_count": 1,
        },
    }
    logger.info("TikTok: requesting upload URL for %s (%d bytes)", video_path.name, video_size)

    init_resp = httpx.post(
        INIT_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json=init_payload,
        timeout=30.0,
    )
    init_resp.raise_for_status()
    init_data = init_resp.json()["data"]
    upload_url = init_data["upload_url"]
    publish_id = init_data["publish_id"]

    logger.info("TikTok: uploading binary, publish_id=%s", publish_id)
    with video_path.open("rb") as fh:
        body = fh.read()

    put_resp = httpx.put(
        upload_url,
        content=body,
        headers={
            "Content-Type": "video/mp4",
            "Content-Length": str(video_size),
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        },
        timeout=300.0,
    )
    put_resp.raise_for_status()

    logger.info("TikTok: %s uploaded, publish_id=%s. Caption to apply: %s", video_path.name, publish_id, title[:60])
    return publish_id
