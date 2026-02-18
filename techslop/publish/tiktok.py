"""TikTok upload stub."""

from pathlib import Path


def upload_to_tiktok(video_path: Path, title: str) -> str:
    """Upload a video to TikTok.

    Not yet implemented.

    Args:
        video_path: Local path to the video file.
        title: Video title / caption.

    Returns:
        The TikTok video ID.

    Raises:
        NotImplementedError: Always, until the TikTok API integration is built.
    """
    raise NotImplementedError("TikTok upload not yet implemented")
