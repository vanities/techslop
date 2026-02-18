"""Generate background images and branding elements for TechSlop videos."""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Dark gradient colors (top to bottom)
GRADIENT_TOP = (10, 10, 40)      # Dark navy
GRADIENT_BOTTOM = (30, 10, 50)   # Dark purple

# Text styling
TEXT_COLOR = (255, 255, 255)
TITLE_PADDING = 80
PREFERRED_FONTS = [
    "Montserrat-Bold",
    "Arial Black",
    "ArialBlack",
    "Helvetica-Bold",
    "DejaVuSans-Bold",
]


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a preferred bold font, falling back to the default."""
    for font_name in PREFERRED_FONTS:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    # Fallback: Pillow's built-in default font (scaled via size parameter)
    try:
        return ImageFont.truetype("Arial", size)
    except OSError:
        return ImageFont.load_default()


def generate_background(
    output_path: Path, width: int = 1080, height: int = 1920
) -> Path:
    """Create a dark vertical gradient background image (navy to purple).

    Args:
        output_path: Path where the PNG image will be saved.
        width: Image width in pixels. Defaults to 1080.
        height: Image height in pixels. Defaults to 1920.

    Returns:
        The output_path after writing the file.
    """
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        ratio = y / height
        r = int(GRADIENT_TOP[0] + (GRADIENT_BOTTOM[0] - GRADIENT_TOP[0]) * ratio)
        g = int(GRADIENT_TOP[1] + (GRADIENT_BOTTOM[1] - GRADIENT_TOP[1]) * ratio)
        b = int(GRADIENT_TOP[2] + (GRADIENT_BOTTOM[2] - GRADIENT_TOP[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    image.save(str(output_path), "PNG")
    logger.info("Background image saved to %s (%dx%d)", output_path, width, height)
    return output_path


def generate_title_card(
    title: str, output_path: Path, width: int = 1080, height: int = 1920
) -> Path:
    """Create a title card image with a headline centered on a dark background.

    The text is word-wrapped to fit within horizontal padding and centered
    vertically on the image.

    Args:
        title: The headline text to display.
        output_path: Path where the PNG image will be saved.
        width: Image width in pixels. Defaults to 1080.
        height: Image height in pixels. Defaults to 1920.

    Returns:
        The output_path after writing the file.
    """
    # Start with a gradient background
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        ratio = y / height
        r = int(GRADIENT_TOP[0] + (GRADIENT_BOTTOM[0] - GRADIENT_TOP[0]) * ratio)
        g = int(GRADIENT_TOP[1] + (GRADIENT_BOTTOM[1] - GRADIENT_TOP[1]) * ratio)
        b = int(GRADIENT_TOP[2] + (GRADIENT_BOTTOM[2] - GRADIENT_TOP[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Determine font size and wrap text to fit
    max_text_width = width - (TITLE_PADDING * 2)
    font_size = 72
    font = _get_font(font_size)

    # Estimate characters per line from available width and font
    # Use a conservative estimate then adjust by actual measurement
    wrapped_lines = textwrap.wrap(title, width=20)

    # Reduce font size if text is too wide
    while font_size > 24:
        font = _get_font(font_size)
        too_wide = False
        for line in wrapped_lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            if line_width > max_text_width:
                too_wide = True
                break
        if not too_wide:
            break
        font_size -= 4
        wrapped_lines = textwrap.wrap(title, width=int(20 * 72 / font_size))

    # Calculate total text block height
    line_spacing = int(font_size * 1.4)
    total_text_height = line_spacing * len(wrapped_lines)

    # Draw text centered vertically and horizontally
    y_start = (height - total_text_height) // 2

    for i, line in enumerate(wrapped_lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (width - line_width) // 2
        y = y_start + i * line_spacing
        # Draw shadow for readability
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=TEXT_COLOR)

    image.save(str(output_path), "PNG")
    logger.info("Title card saved to %s", output_path)
    return output_path
