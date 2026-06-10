"""FFmpeg-based video assembly for techslop shorts.

Two modes:

* ``assemble_video_static`` — original behavior. Loops one background image
  for the audio duration, burns captions, watermark. Cheap fallback.
* ``assemble_video_motion`` — concatenates N Kling/Seedance motion clips with
  crossfade transitions, syncs to audio, burns captions + watermark + optional
  title overlay. This is the v2 default once you have grid + i2v wired up.

Both output 1080x1920 H.264 MP4 with AAC audio at 30fps.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

CROSSFADE_SECONDS = 0.5
TARGET_W, TARGET_H = 1080, 1920


def get_audio_duration(audio_path: Path) -> float:
    """Get the duration of an audio file in seconds via ffprobe."""
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
    duration = float(json.loads(result.stdout)["format"]["duration"])
    logger.info("Audio duration for %s: %.2fs", audio_path.name, duration)
    return duration


def get_video_duration(video_path: Path) -> float:
    """Get the duration of a video file in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def _ass_path_filter(captions_path: Path) -> str:
    """Escape an ASS path for use inside an ffmpeg filtergraph string."""
    return str(captions_path).replace("\\", "\\\\").replace(":", "\\:")


def _watermark_filter() -> str:
    return (
        "drawtext="
        "text='techslop':"
        "fontsize=28:"
        "fontcolor=white@0.5:"
        "borderw=1:"
        "bordercolor=black@0.3:"
        "x=w-text_w-30:"
        "y=h-text_h-30"
    )


def _title_filter(title: str, duration_visible: float = 2.0) -> str:
    safe_title = title.replace("'", "’").replace(":", "\\:")
    return (
        f"drawtext="
        f"text='{safe_title}':"
        f"fontsize=56:"
        f"fontcolor=white:"
        f"borderw=3:"
        f"bordercolor=black:"
        f"x=(w-text_w)/2:"
        f"y=(h/4)-text_h/2:"
        f"enable='between(t,0,{duration_visible})'"
    )


# ---------------------------------------------------------------------------
# Static-image assembly (legacy)
# ---------------------------------------------------------------------------


def assemble_video_static(
    audio_path: Path,
    captions_path: Path,
    background_path: Path,
    output_path: Path,
    title: str = "",
    duration: float | None = None,
) -> Path:
    """Original techslop assembly: loop one image, overlay audio + captions + watermark."""
    if duration is None:
        duration = get_audio_duration(audio_path)

    filters: list[str] = [f"ass='{_ass_path_filter(captions_path)}'"]
    if title:
        filters.append(_title_filter(title))
    filters.append(_watermark_filter())

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(background_path),
        "-i", str(audio_path),
        "-vf", ",".join(filters),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-r", "30",
        "-s", f"{TARGET_W}x{TARGET_H}",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(duration),
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    logger.info("Static video assembled: %s (%.1fs)", output_path, duration)
    return output_path


# Backwards-compat alias for callers that import the old name.
assemble_video = assemble_video_static


# ---------------------------------------------------------------------------
# Motion-clip assembly (v2)
# ---------------------------------------------------------------------------


def _build_xfade_chain(n_clips: int, durations: list[float], crossfade: float) -> tuple[str, str]:
    """Build the xfade filter chain for N clips.

    Returns (filtergraph_segment, final_label). The final_label is the [vN]
    label produced by the chain — caller appends additional filters on top.
    """
    if n_clips == 1:
        return ("[0:v]null[v0]", "v0")

    parts: list[str] = []

    # Normalize each clip to TARGET_W x TARGET_H, 30fps, yuv420p, with consistent SAR
    for i in range(n_clips):
        parts.append(
            f"[{i}:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},setsar=1,fps=30,format=yuv420p[v{i}n]"
        )

    # Chain xfade: [v0n][v1n]xfade=transition=fade:duration=X:offset=O[v01]
    # Each successive xfade offsets at (sum of prior durations) - (i * crossfade)
    cumulative = 0.0
    last_label = "v0n"
    for i in range(1, n_clips):
        cumulative += durations[i - 1] - crossfade
        new_label = f"v0{i}" if i == 1 else f"v0{i}"
        parts.append(
            f"[{last_label}][v{i}n]xfade=transition=fade:duration={crossfade}:"
            f"offset={cumulative:.3f}[{new_label}]"
        )
        last_label = new_label

    return (";".join(parts), last_label)


def assemble_video_motion(
    clip_paths: list[Path],
    audio_path: Path,
    captions_path: Path,
    output_path: Path,
    title: str = "",
    crossfade: float = CROSSFADE_SECONDS,
) -> Path:
    """Concatenate motion clips with crossfades, sync to audio, overlay captions.

    Args:
        clip_paths: Ordered list of motion-clip MP4s (e.g. from Kling).
        audio_path: Narration audio (mp3/wav). Determines final video length.
        captions_path: ASS subtitle file (karaoke captions).
        output_path: Where the final MP4 lands.
        title: Optional title text shown for the first 2 seconds.
        crossfade: Crossfade duration between clips (seconds).
    """
    if not clip_paths:
        raise ValueError("clip_paths must contain at least one clip")

    audio_duration = get_audio_duration(audio_path)
    clip_durations = [get_video_duration(c) for c in clip_paths]

    chain_filters, final_video_label = _build_xfade_chain(
        len(clip_paths), clip_durations, crossfade
    )

    # Append captions / title / watermark on top of the xfade output
    overlay_chain = [f"[{final_video_label}]ass='{_ass_path_filter(captions_path)}'"]
    if title:
        overlay_chain.append(_title_filter(title))
    overlay_chain.append(_watermark_filter())
    overlay_chain.append("[vfinal]")
    overlay_filter = ",".join(overlay_chain[:-1]) + overlay_chain[-1]

    full_filter = chain_filters + ";" + overlay_filter

    cmd = ["ffmpeg", "-y"]
    for clip in clip_paths:
        cmd.extend(["-i", str(clip)])
    cmd.extend(["-i", str(audio_path)])

    cmd.extend([
        "-filter_complex", full_filter,
        "-map", "[vfinal]",
        "-map", f"{len(clip_paths)}:a",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(audio_duration),
        "-shortest",
        str(output_path),
    ])

    logger.info(
        "Assembling motion video: %d clips, %.1fs audio, crossfade=%.2fs",
        len(clip_paths), audio_duration, crossfade,
    )
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    logger.info("Motion video assembled: %s", output_path)
    return output_path
