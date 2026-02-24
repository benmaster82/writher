"""Centralised Pandora Blackboard brand assets for Writher.

Provides reusable eye-icon rendering at any size, used by:
- tray_icon.py  (system tray)
- notes_window.py  (title bar)
- notifier.py  (toast notification icon)
"""

import os
from PIL import Image, ImageDraw, ImageFilter

# ── Eye geometry ratios (relative to output size) ─────────────────────────
_EYE_SPREAD_RATIO = 0.18   # half-distance between dots / size
_EYE_RADIUS_RATIO = 0.10   # dot radius / size (larger = crisper at small sizes)
_GLOW_MULT = 2.8           # glow radius multiplier

# ── Paths ─────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
_ICO_PATH = os.path.join(_DIR, "writher.ico")
_PNG_PATH = os.path.join(_DIR, "writher_icon.png")


def render_eyes(
    size: int = 64,
    bg_rgb: tuple = (12, 12, 15),
    eye_rgb: tuple = (255, 255, 255),
    glow_rgb: tuple | None = None,
    glow_alpha: int = 60,
    circle_bg: bool = True,
    bg_alpha: int = 255,
) -> Image.Image:
    """Render the Pandora Blackboard [ · · ] eyes as a PIL RGBA image.

    Args:
        size:       Output image size (square).
        bg_rgb:     Background fill colour. Ignored if circle_bg is False.
        eye_rgb:    Core eye dot colour.
        glow_rgb:   Glow colour (defaults to eye_rgb).
        glow_alpha: Glow layer opacity (0-255).
        circle_bg:  If True, draw a filled circle background.
        bg_alpha:   Background circle alpha (0-255). Use 0 for transparent bg.

    Returns:
        PIL Image in RGBA mode.
    """
    if glow_rgb is None:
        glow_rgb = eye_rgb

    # Higher internal scale for crisp output at all sizes
    scale = 8
    s = size * scale
    cx = s // 2
    cy = s // 2
    spread = size * _EYE_SPREAD_RATIO * scale
    er = size * _EYE_RADIUS_RATIO * scale

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Optional circular background
    if circle_bg and bg_alpha > 0:
        pad = int(s * 0.04)
        draw.ellipse([pad, pad, s - pad, s - pad],
                     fill=bg_rgb + (bg_alpha,))

    lx = cx - spread
    rx = cx + spread

    # Glow layer (soft light behind the dots)
    glow_img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    gr = er * _GLOW_MULT
    glow_draw.ellipse([lx - gr, cy - gr, lx + gr, cy + gr],
                      fill=glow_rgb + (glow_alpha,))
    glow_draw.ellipse([rx - gr, cy - gr, rx + gr, cy + gr],
                      fill=glow_rgb + (glow_alpha,))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=er * 1.5))
    img = Image.alpha_composite(img, glow_img)

    # Core dots
    draw = ImageDraw.Draw(img)
    draw.ellipse([lx - er, cy - er, lx + er, cy + er], fill=eye_rgb + (255,))
    draw.ellipse([rx - er, cy - er, rx + er, cy + er], fill=eye_rgb + (255,))

    return img.resize((size, size), Image.LANCZOS)


def make_tray_icon(recording: bool = False) -> Image.Image:
    """Generate a 64x64 tray icon with Pandora eyes.

    Idle: white eyes on dark circle.
    Recording: red-tinted eyes with red glow.
    """
    if recording:
        return render_eyes(
            size=64,
            bg_rgb=(50, 12, 12),
            eye_rgb=(255, 80, 80),
            glow_rgb=(255, 50, 50),
            glow_alpha=80,
        )
    return render_eyes(
        size=64,
        bg_rgb=(15, 15, 20),
        eye_rgb=(255, 255, 255),
        glow_rgb=(255, 255, 255),
        glow_alpha=55,
    )


def make_title_bar_image(size: int = 20) -> Image.Image:
    """Small transparent eyes for the notes window title bar."""
    return render_eyes(
        size=size,
        eye_rgb=(91, 206, 250),
        glow_rgb=(91, 206, 250),
        glow_alpha=45,
        circle_bg=False,
    )


def get_notification_icon_path() -> str:
    """Return path to a high-res PNG for toast notifications.

    Generates the file on first call. PNG is preferred over ICO for
    Windows toast notifications — sharper rendering and no scaling artifacts.
    """
    if not os.path.exists(_PNG_PATH):
        _generate_notification_png()
    return _PNG_PATH


def get_ico_path() -> str:
    """Return path to writher.ico, generating it if missing."""
    if not os.path.exists(_ICO_PATH):
        _generate_ico()
    return _ICO_PATH


def _generate_notification_png():
    """Generate a 256x256 PNG with transparent background for toast icons.

    Transparent background lets the notification blend with the Windows
    theme (dark or light) instead of showing an ugly dark square.
    """
    size = 256
    img = render_eyes(
        size=size,
        eye_rgb=(255, 255, 255),
        glow_rgb=(255, 255, 255),
        glow_alpha=70,
        circle_bg=True,
        bg_rgb=(30, 30, 40),
        bg_alpha=200,
    )
    img.save(_PNG_PATH, format="PNG")


def _generate_ico():
    """Generate a multi-size .ico file with the Pandora eyes."""
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    for sz in sizes:
        img = render_eyes(
            size=sz,
            bg_rgb=(15, 15, 20),
            eye_rgb=(255, 255, 255),
            glow_rgb=(255, 255, 255),
            glow_alpha=55,
        )
        images.append(img)

    images[0].save(
        _ICO_PATH,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=images[1:],
    )
