"""LinkedIn video publishing via the Marketing / UGC Posts API.

Posts as either a person or an organization. For solo dev experiments,
posting as a person (your own profile) is the simplest path and only needs:
    - A LinkedIn app with w_member_social scope
    - A user access token (3-legged OAuth)

Env vars:
    LINKEDIN_ACCESS_TOKEN  — bearer token
    LINKEDIN_OWNER_URN     — e.g. "urn:li:person:abcd..." or
                             "urn:li:organization:1234567"

Three-step flow:
    1. POST /v2/assets?action=registerUpload  → upload URL + asset URN
    2. PUT the binary to the upload URL
    3. POST /v2/ugcPosts referencing the asset URN

Reference:
https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from techslop.config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.linkedin.com"


def _require_creds() -> None:
    if not (settings.linkedin_access_token and settings.linkedin_owner_urn):
        raise RuntimeError(
            "LinkedIn credentials missing. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_OWNER_URN in .env"
        )


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.linkedin_access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def _register_upload() -> tuple[str, str]:
    """Returns (upload_url, asset_urn)."""
    payload = {
        "registerUploadRequest": {
            "owner": settings.linkedin_owner_urn,
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
            "serviceRelationships": [
                {"identifier": "urn:li:userGeneratedContent", "relationshipType": "OWNER"}
            ],
            "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"],
        }
    }
    r = httpx.post(
        f"{API_BASE}/v2/assets?action=registerUpload",
        headers=_headers(),
        json=payload,
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()["value"]
    upload_url = data["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_urn = data["asset"]
    return upload_url, asset_urn


def _upload_binary(upload_url: str, video_path: Path) -> None:
    body = video_path.read_bytes()
    r = httpx.put(
        upload_url,
        content=body,
        headers={"Authorization": f"Bearer {settings.linkedin_access_token}"},
        timeout=300.0,
    )
    r.raise_for_status()


def _create_ugc_post(asset_urn: str, title: str, description: str) -> str:
    payload = {
        "author": settings.linkedin_owner_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": description or title},
                "shareMediaCategory": "VIDEO",
                "media": [
                    {
                        "status": "READY",
                        "description": {"text": description or title},
                        "media": asset_urn,
                        "title": {"text": title},
                    }
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    r = httpx.post(
        f"{API_BASE}/v2/ugcPosts",
        headers=_headers(),
        json=payload,
        timeout=30.0,
    )
    r.raise_for_status()
    return r.headers.get("x-restli-id") or r.json().get("id", "")


def upload_to_linkedin(video_path: Path, title: str, description: str = "") -> str:
    """Upload a video and create a UGC post. Returns the post URN."""
    _require_creds()

    logger.info("LinkedIn: registering upload for %s", video_path.name)
    upload_url, asset_urn = _register_upload()

    logger.info("LinkedIn: uploading binary to asset %s", asset_urn)
    _upload_binary(upload_url, video_path)

    # LinkedIn processes the asset async — give it a moment before posting.
    time.sleep(3)

    logger.info("LinkedIn: creating UGC post")
    post_id = _create_ugc_post(asset_urn=asset_urn, title=title, description=description)
    logger.info("LinkedIn: published post=%s", post_id)
    return post_id
