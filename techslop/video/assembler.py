"""FFmpeg-based video assembly for TechSlop shorts."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def get_audio_duration(audio_path: Path) -> float:
    """Get the duration of an audio file in seconds using ffprobe.

    Args:
        audio_path: Path to the audio file.

    Returns:
        Duration in seconds as a float.

    Raises:
        subprocess.CalledProcessError: If ffprobe fails.
        ValueError: If the duration cannot be parsed.
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    probe_data = json.loads(result.stdout)
    duration = float(probe_data["format"]["duration"])
    logger.info("Audio duration for %s: %.2fs", audio_path.name, duration)
    return duration


def assemble_video(
    audio_path: Path,
    captions_path: Path,
    background_path: Path,
    output_path: Path,
    title: str = "",
    duration: float | None = None,
) -> Path:
    """Assemble a vertical short-form video from audio, captions, and a background image.

    Pipeline:
        1. Loop background image as video for the audio duration
        2. Overlay audio track
        3. Burn in ASS subtitles (karaoke-style captions)
        4. Optionally add a title card overlay for the first 2 seconds
        5. Add a "techslop" watermark in the lower-right corner

    Output is 1080x1920 H.264 MP4 with AAC audio at 30fps.

    Args:
        audio_path: Path to the narration audio file.
        captions_path: Path to the ASS subtitle file.
        background_path: Path to the background image (PNG).
        output_path: Path where the final MP4 will be written.
        title: Optional title text to display for the first 2 seconds.
        duration: Audio duration in seconds. If None, it will be probed.

    Returns:
        The output_path after writing the file.

    Raises:
        subprocess.CalledProcessError: If ffmpeg fails.
    """
    if duration is None:
        duration = get_audio_duration(audio_path)

    # Build the filtergraph
    filters: list[str] = []

    # Burn in ASS subtitles
    # Escape colons and backslashes in the path for the ass filter
    ass_path_escaped = str(captions_path).replace("\\", "\\\\").replace(":", "\\:")
    filters.append(f"ass='{ass_path_escaped}'")

    # Title card overlay for the first 2 seconds
    if title:
        # Escape single quotes and colons in title text for drawtext
        safe_title = title.replace("'", "\u2019").replace(":", "\\:")
        filters.append(
            f"drawtext="
            f"text='{safe_title}':"
            f"fontfile='':"
            f"fontsize=56:"
            f"fontcolor=white:"
            f"borderw=3:"
            f"bordercolor=black:"
            f"x=(w-text_w)/2:"
            f"y=(h/4)-text_h/2:"
            f"enable='between(t,0,2)'"
        )

    # Watermark: "techslop" in the lower-right corner
    filters.append(
        "drawtext="
        "text='techslop':"
        "fontsize=28:"
        "fontcolor=white@0.5:"
        "borderw=1:"
        "bordercolor=black@0.3:"
        "x=w-text_w-30:"
        "y=h-text_h-30"
    )

    filtergraph = ",".join(filters)

    cmd = [
        "ffmpeg",
        "-y",
        # Loop the background image as video input
        "-loop", "1",
        "-i", str(background_path),
        # Audio input
        "-i", str(audio_path),
        # Apply filtergraph
        "-vf", filtergraph,
        # Video settings
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-r", "30",
        "-s", "1080x1920",
        "-pix_fmt", "yuv420p",
        # Audio settings
        "-c:a", "aac",
        "-b:a", "192k",
        # Duration: match audio length
        "-t", str(duration),
        # Use shortest stream to determine duration
        "-shortest",
        # Output
        str(output_path),
    ]

    logger.info("Assembling video: %s", " ".join(cmd))

    subprocess.run(cmd, check=True, capture_output=True, text=True)

    logger.info("Video assembled: %s (%.1fs)", output_path, duration)
    return output_path
