"""YouTube Shorts upload via YouTube Data API v3."""

from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from techslop.config import settings

_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB


def upload_to_youtube(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str] | None = None,
) -> str:
    """Upload a video to YouTube as a Short.

    Args:
        video_path: Local path to the video file.
        title: Video title. ``#Shorts`` is appended automatically if not
            already present so YouTube recognises it as a Short.
        description: Video description text.
        tags: Optional list of tags for the video.

    Returns:
        The YouTube video ID of the uploaded video.
    """
    if "#Shorts" not in title:
        title = f"{title} #Shorts"

    creds = Credentials(
        token=None,
        refresh_token=settings.youtube_refresh_token,
        client_id=settings.youtube_client_id,
        client_secret=settings.youtube_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": "public",
            "madeForKids": False,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        resumable=True,
        chunksize=_CHUNK_SIZE,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id: str = response["id"]
    return video_id
