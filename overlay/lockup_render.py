"""Programmatically render a Sports Direct-style word lockup as a transparent PNG.

Mirrors the visual language of the SD lockups in the asset pack:
- GT America Extended Black Italic, all caps
- Words separated by thin vertical bar dividers
- "mixed" style alternates between solid-fill and outlined words (like the
  GOLF|STARTS|HERE lockup); "solid" fills every word; "outline" strokes every
  word.
- Optional small rounded-rectangle chip to the right (e.g. "70% OFF") with a
  thin border and same-color text.

Output is a high-resolution transparent PNG which the existing compose pipeline
scales into the target rect on the campaign image.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

ASSETS_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
DEFAULT_SD_FONT = ASSETS_FONTS / "sports-direct" / "GT-America-Extended-Black-Italic.otf"
DEFAULT_FRASERS_FONT = ASSETS_FONTS / "frasers" / "ABCWhyteInktrap-Light.otf"
DEFAULT_FLANNELS_FONT = ASSETS_FONTS / "flannels" / "RomainHeadline-Regular.otf"

Style = Literal["solid", "outline", "mixed"]


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _resolve_font(font_path: str | Path | None, brand: str | None) -> Path:
    if font_path is not None:
        p = Path(font_path)
        if not p.exists():
            raise FileNotFoundError(f"font not found: {p}")
        return p
    if brand == "frasers":
        candidate = DEFAULT_FRASERS_FONT
    elif brand == "flannels":
        candidate = DEFAULT_FLANNELS_FONT
    else:
        candidate = DEFAULT_SD_FONT
    if not candidate.exists():
        raise FileNotFoundError(
            f"default font not found: {candidate}. Place the .otf file under assets/fonts/<brand>/, "
            f"or pass font_path explicitly."
        )
    return candidate


def make_lockup(
    text: str,
    *,
    chip: str | None = None,
    style: Style = "mixed",
    font_path: str | Path | None = None,
    brand: str | None = None,
    color: str = "#FFFFFF",
    height_px: int = 720,
) -> Image.Image:
    """Render a horizontal word lockup as a transparent RGBA PNG.

    text: words separated by '|', e.g. "RUGBY|STARTS|HERE".
    chip: optional small bracketed text on the right, e.g. "70% OFF".
    style: 'solid' (all filled), 'outline' (all stroked), 'mixed' (alternate).
    color: hex color for text and chip border.
    height_px: output height; width is computed from text length.
    """
    font_file = _resolve_font(font_path, brand)
    words = [w.strip() for w in text.split("|") if w.strip()]
    if not words:
        raise ValueError("text must contain at least one non-empty word")

    rgba = _hex_to_rgba(color)

    # Sizing: cap-height ≈ ~70% of font size; aim for cap-height ≈ 88% of canvas height.
    font_size = int(height_px * 0.92)
    font = ImageFont.truetype(str(font_file), font_size)
    stroke_w = max(2, int(font_size * 0.045))

    word_widths: list[int] = []
    for w in words:
        bbox = font.getbbox(w, stroke_width=stroke_w)
        word_widths.append(bbox[2] - bbox[0])

    word_gap = int(font_size * 0.30)
    divider_w = max(2, int(font_size * 0.045))

    n = len(words)
    total_w = sum(word_widths) + (n - 1) * (word_gap + divider_w + word_gap)

    chip_font: ImageFont.FreeTypeFont | None = None
    chip_w = chip_h = chip_text_w = chip_text_h = 0
    chip_pad_x = chip_pad_y = chip_gap = 0
    chip_bbox = (0, 0, 0, 0)
    if chip:
        chip_font_size = int(font_size * 0.42)
        chip_font = ImageFont.truetype(str(font_file), chip_font_size)
        chip_bbox = chip_font.getbbox(chip)
        chip_text_w = chip_bbox[2] - chip_bbox[0]
        chip_text_h = chip_bbox[3] - chip_bbox[1]
        chip_pad_x = int(chip_font_size * 0.55)
        chip_pad_y = int(chip_font_size * 0.30)
        chip_w = chip_text_w + 2 * chip_pad_x
        chip_h = chip_text_h + 2 * chip_pad_y
        chip_gap = int(font_size * 0.40)
        total_w += chip_gap + chip_w

    pad = int(font_size * 0.10)
    canvas_w = total_w + 2 * pad
    canvas_h = height_px

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Use uppercase reference letters to compute a stable cap-band y-position.
    cap_bbox = font.getbbox("MGAB")
    cap_h = cap_bbox[3] - cap_bbox[1]
    y = (canvas_h - cap_h) // 2 - cap_bbox[1]

    x = pad
    for i, w in enumerate(words):
        per_word_style = style
        if style == "mixed":
            per_word_style = "solid" if (i % 2 == 0) else "outline"

        if per_word_style == "solid":
            draw.text((x, y), w, font=font, fill=rgba)
        else:
            draw.text(
                (x, y),
                w,
                font=font,
                fill=(0, 0, 0, 0),
                stroke_width=stroke_w,
                stroke_fill=rgba,
            )

        x += word_widths[i]
        if i < n - 1:
            x += word_gap
            div_top = y + cap_bbox[1] + int(cap_h * 0.04)
            div_bot = y + cap_bbox[1] + cap_h - int(cap_h * 0.04)
            draw.rectangle([x, div_top, x + divider_w, div_bot], fill=rgba)
            x += divider_w + word_gap

    if chip and chip_font is not None:
        x += chip_gap
        cy = (canvas_h - chip_h) // 2
        border_w = max(2, int(font_size * 0.04))
        draw.rounded_rectangle(
            [x, cy, x + chip_w, cy + chip_h],
            outline=rgba,
            width=border_w,
            radius=max(4, int(chip_h * 0.18)),
        )
        ctext_x = x + chip_pad_x - chip_bbox[0]
        ctext_y = cy + chip_pad_y - chip_bbox[1]
        draw.text((ctext_x, ctext_y), chip, font=chip_font, fill=rgba)

    # Trim transparent margins for tight bbox
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    return img


def make_stacked_lockup(
    lines: list[str],
    *,
    style: Style = "mixed",
    font_path: str | Path | None = None,
    brand: str | None = None,
    color: str = "#FFFFFF",
    line_height_px: int = 360,
    line_spacing: float = 0.0,
) -> Image.Image:
    """Render a multi-line horizontal lockup (each list element is its own row).

    Each row is rendered via make_lockup; rows are stacked vertically, centered.
    Useful for "MOTHER'S DAY / GIFTING"-style two-liners.
    """
    rendered = [
        make_lockup(
            line,
            style=style,
            font_path=font_path,
            brand=brand,
            color=color,
            height_px=line_height_px,
        )
        for line in lines
    ]
    gap = int(line_height_px * line_spacing)
    total_h = sum(r.size[1] for r in rendered) + gap * (len(rendered) - 1)
    total_w = max(r.size[0] for r in rendered)
    canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 0
    for r in rendered:
        x = (total_w - r.size[0]) // 2
        canvas.paste(r, (x, y), r)
        y += r.size[1] + gap
    return canvas
