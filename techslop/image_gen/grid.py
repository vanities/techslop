"""gpt-image-2 grid generation for character-consistent multi-shot keyframes.

One API call returns a single grid image (e.g. 2x2) where every panel shows
the same character/setting in a different scene. Splitting the grid yields
i2v-ready keyframes that share visual identity, which is the cheapest known
trick for character consistency across motion shots.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import openai

from techslop.config import settings
from techslop.models import Script

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "2048x2048"


def build_grid_prompt(script: Script, character_brief: str = "") -> str:
    """Build the grid prompt from a Script's body sections.

    Each body section's screen_text becomes one panel description. Panels are
    laid out left-to-right, top-to-bottom in the grid.
    """
    panels = [s.screen_text or s.text[:80] for s in script.body]
    rows, cols = grid_shape(len(panels))

    lines = [
        f"A {rows}x{cols} grid of {len(panels)} cinematic vertical 9:16 shots, "
        f"laid out left-to-right, top-to-bottom.",
    ]
    if character_brief:
        lines.append(f"Character: {character_brief}")
    lines.append(
        "Critical: the same character (identical face, hair, outfit) appears in EVERY panel. "
        "Same lighting style, same color grade, same aesthetic across all panels. "
        "Each panel is a different scene from the same story."
    )
    lines.append("Panels:")
    for i, panel in enumerate(panels, 1):
        lines.append(f"  {i}. {panel}")
    return "\n".join(lines)


def grid_shape(n: int) -> tuple[int, int]:
    """Pick (rows, cols) for n panels. Prefers square-ish layouts."""
    if n <= 1:
        return (1, 1)
    if n == 2:
        return (1, 2)
    if n <= 4:
        return (2, 2)
    if n <= 6:
        return (2, 3)
    if n <= 9:
        return (3, 3)
    return (3, 4)


def generate_grid(
    script: Script,
    output_path: Path,
    character_brief: str = "",
    size: str = DEFAULT_SIZE,
) -> Path:
    """Generate one grid image for an entire Script via gpt-image-2.

    Args:
        script: Script with body sections — each section becomes one grid panel.
        output_path: Where to write the PNG.
        character_brief: Optional one-line description of the recurring character
            (e.g. "30s tech-bro narrator, denim jacket, glasses").
        size: gpt-image-2 size string (default 2048x2048).

    Returns:
        output_path after writing the file.
    """
    client = openai.OpenAI(api_key=settings.openai_api_key)
    prompt = build_grid_prompt(script, character_brief=character_brief)

    logger.info("Generating grid (%d panels) via gpt-image-2…", len(script.body))
    logger.debug("Grid prompt:\n%s", prompt)

    response = client.images.generate(
        model=DEFAULT_MODEL,
        prompt=prompt,
        size=size,
        n=1,
    )

    b64 = response.data[0].b64_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(base64.b64decode(b64))

    logger.info("Grid written: %s", output_path)
    return output_path
