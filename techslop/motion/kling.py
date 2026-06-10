"""Kling 2.1 Pro image-to-video via fal.ai.

Each panel image becomes a 5-second 9:16 motion clip. Costs ~$1.40/clip.
Run shots in parallel for a 4-shot script: ~$5.60, ~90s wall-clock.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import fal_client
import httpx

from techslop.config import settings

logger = logging.getLogger(__name__)

KLING_MODEL = "fal-ai/kling-video/v2.1/pro/image-to-video"
DEFAULT_DURATION = "5"  # seconds; "5" or "10" for Kling 2.1 Pro
DEFAULT_ASPECT = "9:16"


def _ensure_fal_key() -> None:
    if not settings.fal_key:
        raise RuntimeError("FAL_KEY not set in .env")
    os.environ["FAL_KEY"] = settings.fal_key


async def animate_shot(
    image_path: Path,
    motion_prompt: str,
    output_path: Path,
    duration: str = DEFAULT_DURATION,
    aspect_ratio: str = DEFAULT_ASPECT,
) -> Path:
    """Animate one keyframe via Kling i2v, write the resulting MP4 to output_path.

    Args:
        image_path: Path to the keyframe PNG.
        motion_prompt: Description of the motion (e.g. "slow push-in, subtle
            head turn left"). Keep concise; Kling rewards short prompts.
        output_path: Where the MP4 lands.
        duration: "5" or "10" seconds.
        aspect_ratio: "9:16" for vertical Shorts.

    Returns:
        output_path after writing.
    """
    _ensure_fal_key()

    logger.info("Uploading %s for Kling…", image_path.name)
    image_url = await asyncio.to_thread(fal_client.upload_file, str(image_path))

    logger.info("Submitting Kling i2v job (%ss, %s)…", duration, aspect_ratio)
    handler = await asyncio.to_thread(
        fal_client.submit,
        KLING_MODEL,
        arguments={
            "prompt": motion_prompt,
            "image_url": image_url,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
        },
    )

    result = await asyncio.to_thread(handler.get)
    video_url = result["video"]["url"]

    logger.info("Downloading Kling clip → %s", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.get(video_url)
        r.raise_for_status()
        output_path.write_bytes(r.content)

    return output_path


async def animate_shots(
    image_paths: list[Path],
    motion_prompts: list[str],
    output_dir: Path,
    duration: str = DEFAULT_DURATION,
) -> list[Path]:
    """Animate N shots in parallel. Returns clip paths in input order."""
    if len(image_paths) != len(motion_prompts):
        raise ValueError(
            f"image_paths ({len(image_paths)}) and motion_prompts ({len(motion_prompts)}) must match"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = [
        animate_shot(
            image_path=img,
            motion_prompt=prompt,
            output_path=output_dir / f"clip_{i + 1}.mp4",
            duration=duration,
        )
        for i, (img, prompt) in enumerate(zip(image_paths, motion_prompts))
    ]

    return await asyncio.gather(*tasks)
