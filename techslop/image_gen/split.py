"""Split a grid image into individual panel PNGs."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def split_grid(
    grid_path: Path,
    rows: int,
    cols: int,
    output_dir: Path,
    prefix: str = "shot",
) -> list[Path]:
    """Crop a grid image into rows*cols individual panel PNGs.

    Panels are emitted in reading order (left-to-right, top-to-bottom) and
    numbered 1..N to match the grid prompt.

    Args:
        grid_path: Path to the grid PNG.
        rows: Number of rows in the grid.
        cols: Number of columns.
        output_dir: Directory where shot_N.png files are written.
        prefix: Filename prefix (default "shot" → shot_1.png, shot_2.png, ...).

    Returns:
        Paths to the cropped panel PNGs, in reading order.
    """
    img = Image.open(grid_path)
    w, h = img.size
    cell_w, cell_h = w // cols, h // rows

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for r in range(rows):
        for c in range(cols):
            n = r * cols + c + 1
            box = (c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h)
            panel = img.crop(box)
            out = output_dir / f"{prefix}_{n}.png"
            panel.save(out)
            paths.append(out)

    logger.info("Split %s into %d panels (%dx%d)", grid_path.name, len(paths), rows, cols)
    return paths
