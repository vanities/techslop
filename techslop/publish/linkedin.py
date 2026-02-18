"""LinkedIn video publishing stub.

Requires LinkedIn Marketing API access with rw_organization_social scope.
See: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api
"""

from __future__ import annotations

from pathlib import Path


def upload_to_linkedin(video_path: Path, title: str, description: str = "") -> str:
    """Upload a video to LinkedIn.

    TODO: Implement using LinkedIn Marketing API.
    Requires:
      - LINKEDIN_ACCESS_TOKEN in .env
      - Organization ID for posting as a page

    See: https://learn.microsoft.com/en-us/linkedin/marketing/
    """
    raise NotImplementedError(
        "LinkedIn upload not yet implemented. "
        "Requires LinkedIn Marketing API access."
    )
