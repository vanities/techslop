"""Instagram Reels upload stub."""

from pathlib import Path


def upload_to_instagram(video_path: Path, title: str) -> str:
    """Upload a video to Instagram as a Reel.

    Not yet implemented.

    Args:
        video_path: Local path to the video file.
        title: Video title / caption.

    Returns:
        The Instagram media ID.

    Raises:
        NotImplementedError: Always, until the Instagram API integration is built.
    """
    raise NotImplementedError("Instagram upload not yet implemented")
