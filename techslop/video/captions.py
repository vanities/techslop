"""Generate ASS (Advanced SubStation Alpha) subtitle files with karaoke-style highlighting."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ASS file header for 9:16 vertical video (1080x1920)
ASS_HEADER = """\
[Script Info]
Title: TechSlop Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,48,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,40,40,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

WORDS_PER_LINE = 5
HIGHLIGHT_COLOR = "00FFFF"  # Yellow in ASS BGR format (&H00FFFF& = yellow)


def _format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int(round((seconds % 1) * 100))
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def generate_captions(timestamps_path: Path, output_path: Path) -> Path:
    """Generate an ASS subtitle file with karaoke-style word-by-word highlighting.

    Reads word-level timestamps and produces CapCut-style captions where each
    word lights up smoothly as it is spoken, using ASS \\kf tags for a fill effect.

    Words are grouped into lines of ~4-5 words for readability on vertical video.

    Args:
        timestamps_path: Path to JSON file containing word timestamps.
            Expected format: [{"word": str, "start": float, "end": float}, ...]
        output_path: Path where the ASS subtitle file will be written.

    Returns:
        The output_path after writing the file.

    Raises:
        FileNotFoundError: If timestamps_path does not exist.
        json.JSONDecodeError: If the timestamps file is not valid JSON.
        KeyError: If word entries are missing required fields.
    """
    raw = timestamps_path.read_text()
    words = json.loads(raw)

    logger.info("Generating captions from %d words", len(words))

    # Group words into lines
    lines: list[list[dict]] = []
    for i in range(0, len(words), WORDS_PER_LINE):
        lines.append(words[i : i + WORDS_PER_LINE])

    # Build ASS dialogue events
    events: list[str] = []
    for line_words in lines:
        if not line_words:
            continue

        line_start = line_words[0]["start"]
        line_end = line_words[-1]["end"]

        start_ts = _format_ass_time(line_start)
        end_ts = _format_ass_time(line_end)

        # Build karaoke text with \kf tags for smooth fill highlighting
        # \kf duration is in centiseconds
        karaoke_parts: list[str] = []
        for word_info in line_words:
            duration_cs = int(round((word_info["end"] - word_info["start"]) * 100))
            # Ensure minimum duration of 1 centisecond
            duration_cs = max(duration_cs, 1)
            word_text = word_info["word"].strip()
            karaoke_parts.append(
                f"{{\\kf{duration_cs}}}{word_text}"
            )

        karaoke_text = " ".join(karaoke_parts)

        # Apply highlight color as secondary colour override for the karaoke effect
        styled_text = f"{{\\1c&H{HIGHLIGHT_COLOR}&}}{karaoke_text}"

        event = (
            f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{styled_text}"
        )
        events.append(event)

    # Write the complete ASS file
    ass_content = ASS_HEADER + "\n".join(events) + "\n"
    output_path.write_text(ass_content)

    logger.info("Captions written to %s (%d lines)", output_path, len(events))
    return output_path
