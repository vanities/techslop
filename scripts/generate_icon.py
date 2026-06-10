"""Generate the techslop app icon.

Matches the swiftbible / swiftchan brand: peridot → green → cyan diagonal
gradient with a bold black silhouette centered. The silhouette is a play
triangle with three drops dripping below it — "video shorts" + "slop"
in one symbol.

Outputs:
    icon_assets/Icon-Light-1024x1024.png   (canonical)
    icon_assets/Icon-Dark-1024x1024.png    (same shape, darker bg)
    icon_assets/Icon-Tinted-1024x1024.png  (gray on black)
    assets/icon.png                         (1024 light copy for README)
    assets/icon-512.png                     (downscaled for socials)
    assets/icon-256.png                     (downscaled for socials)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
ICON_ASSETS = REPO_ROOT / "icon_assets"
ASSETS = REPO_ROOT / "assets"

CANVAS = 1024
PERIDOT = (191, 217, 0)   # #BFD900 — top-left
GREEN = (51, 204, 102)    # #33CC66 — middle
CYAN = (0, 191, 217)      # #00BFD9 — bottom-right
BLACK = (15, 15, 15)
GRAY = (190, 190, 190)


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def diagonal_gradient(size: int, top_left, mid, bottom_right) -> Image.Image:
    """Three-stop diagonal gradient (top-left → middle → bottom-right)."""
    img = Image.new("RGB", (size, size))
    px = img.load()
    max_d = (size - 1) * 2  # x + y at the bottom-right corner
    for y in range(size):
        for x in range(size):
            t = (x + y) / max_d  # 0 at top-left, 1 at bottom-right
            if t < 0.5:
                color = _lerp(top_left, mid, t * 2)
            else:
                color = _lerp(mid, bottom_right, (t - 0.5) * 2)
            px[x, y] = color
    return img


def _teardrop(cx: int, top_y: int, length: int, width: int) -> list[tuple[float, float]]:
    """Polygon points for a clean teardrop: tip at (cx, top_y), round bottom.

    The bottom half is a true circle of radius width/2 centered at the
    bottom of the drop; the top half tapers to a point.
    """
    import math

    radius = width / 2
    circle_cy = top_y + length - radius

    # Tip
    pts: list[tuple[float, float]] = [(float(cx), float(top_y))]

    # Arc covering the BOTTOM HALF of the circle: start at right equator (0°),
    # sweep clockwise through bottom (90°) up to left equator (180°). PIL's y
    # axis points down, so positive sin values land below the circle's center.
    n = 48
    for i in range(n + 1):
        deg = (180 * i / n)  # 0° → 90° → 180°
        rad = math.radians(deg)
        pts.append((cx + radius * math.cos(rad), circle_cy + radius * math.sin(rad)))

    return pts


def _draw_play_with_drops(
    base: Image.Image,
    fill: tuple[int, int, int] = BLACK,
) -> Image.Image:
    """Draw the techslop silhouette: a centered play triangle with three drops below.

    The drops vary in size and slightly overlap the triangle's bottom edge so
    the whole shape reads as one melting/dripping play button.
    """
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx = CANVAS // 2
    fill_rgba = fill + (255,)

    # ── Play triangle ▶ ──
    # A play triangle's visual center of mass is at 1/3 from its left base.
    # Shift the geometric body left so the visual center hits the canvas center.
    tri_height = 420   # vertical (top-to-bottom)
    tri_width = 420    # horizontal (base-to-apex extension)
    triangle_cy = CANVAS // 2 - 120  # nudge up to leave room for drops

    base_x = cx - tri_width // 3
    apex_x = base_x + tri_width
    top_y = triangle_cy - tri_height // 2
    bot_y = triangle_cy + tri_height // 2

    triangle_pts = [
        (base_x, top_y),
        (base_x, bot_y),
        (apex_x, triangle_cy),
    ]
    draw.polygon(triangle_pts, fill=fill_rgba)

    # ── Three drops dripping out the bottom ──
    # Tips reach UP into the triangle so the silhouette reads as one melting
    # form. Width:length is ~1:1.5 — chunky teardrops, not icicles. Drops are
    # centered around the triangle's visual center (~x=540), not the canvas
    # center, so the silhouette stays balanced under the asymmetric play shape.
    visual_cx = base_x + int(tri_width * 0.4)  # play triangle's visual center
    drops = [
        # (cx_offset, tip_y, length, width)
        (-220, bot_y - 60,  240, 150),   # left
        (0,    bot_y - 30,  300, 190),   # center, biggest, dangles lowest
        (220,  bot_y - 70,  220, 140),   # right
    ]
    for dx, tip_y, length, width in drops:
        pts = _teardrop(visual_cx + dx, tip_y, length, width)
        draw.polygon(pts, fill=fill_rgba)

    return Image.alpha_composite(base.convert("RGBA"), overlay)


def make_light() -> Image.Image:
    bg = diagonal_gradient(CANVAS, PERIDOT, GREEN, CYAN)
    return _draw_play_with_drops(bg).convert("RGB")


def make_dark() -> Image.Image:
    """Same gradient, slightly muted, matching the same silhouette."""
    bg = diagonal_gradient(
        CANVAS,
        _lerp(PERIDOT, BLACK, 0.45),
        _lerp(GREEN, BLACK, 0.45),
        _lerp(CYAN, BLACK, 0.45),
    )
    return _draw_play_with_drops(bg).convert("RGB")


def make_tinted() -> Image.Image:
    """Gray silhouette on solid black, mirrors swiftbible's tinted style."""
    bg = Image.new("RGB", (CANVAS, CANVAS), (0, 0, 0))
    return _draw_play_with_drops(bg, fill=GRAY).convert("RGB")


def main() -> None:
    ICON_ASSETS.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)

    light = make_light()
    dark = make_dark()
    tinted = make_tinted()

    light.save(ICON_ASSETS / "Icon-Light-1024x1024.png", "PNG")
    dark.save(ICON_ASSETS / "Icon-Dark-1024x1024.png", "PNG")
    tinted.save(ICON_ASSETS / "Icon-Tinted-1024x1024.png", "PNG")

    light.save(ASSETS / "icon.png", "PNG")
    light.resize((512, 512), Image.LANCZOS).save(ASSETS / "icon-512.png", "PNG")
    light.resize((256, 256), Image.LANCZOS).save(ASSETS / "icon-256.png", "PNG")

    print(f"Wrote icons to {ICON_ASSETS} and {ASSETS}")


if __name__ == "__main__":
    main()
