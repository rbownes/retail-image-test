from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from overlay.placement import PlacementSpec
from overlay.templates import Template

_PACKAGED_FONT = Path(__file__).parent / "fonts" / "Inter-Bold.otf"


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _load_font(size: int, font_path: str | None) -> ImageFont.FreeTypeFont:
    candidates: list[Path] = []
    if font_path:
        candidates.append(Path(font_path).expanduser())
    candidates.append(_PACKAGED_FONT)
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default(size=size)


def _wrap_to_width(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if font.getlength(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _measure_block(
    lines: list[str], font: ImageFont.FreeTypeFont, line_spacing: float
) -> tuple[int, int]:
    if not lines:
        return (0, 0)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    width = max(int(font.getlength(line)) for line in lines)
    height = int(line_h * len(lines) + line_h * line_spacing * (len(lines) - 1))
    return width, height


def _fit_font_size(
    text: str,
    initial_size: int,
    box_w: int,
    box_h: int,
    font_path: str | None,
    line_spacing: float = 0.2,
    min_size: int = 14,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    size = max(initial_size, min_size)
    while size >= min_size:
        font = _load_font(size, font_path)
        lines = _wrap_to_width(text, font, box_w)
        _, h = _measure_block(lines, font, line_spacing)
        widest = max(font.getlength(line) for line in lines) if lines else 0
        if h <= box_h and widest <= box_w:
            return font, lines
        size = int(size * 0.92)
    font = _load_font(min_size, font_path)
    lines = _wrap_to_width(text, font, box_w)
    return font, lines


def render_overlay(
    image: Image.Image,
    copy: str,
    spec: PlacementSpec,
    font_path: str | None = None,
    template: Template | None = None,
) -> Image.Image:
    base = image.convert("RGBA")
    W, H = base.size

    rx, ry, rw, rh = spec.region
    box_x = int(rx * W)
    box_y = int(ry * H)
    box_w = max(1, int(rw * W))
    box_h = max(1, int(rh * H))

    initial_size = max(14, int(spec.font_size_pct / 100.0 * H))
    line_spacing = 0.2
    font, lines = _fit_font_size(
        copy, initial_size, box_w, box_h, font_path, line_spacing=line_spacing
    )

    text_w, text_h = _measure_block(lines, font, line_spacing)
    if spec.alignment == "center":
        anchor_x = box_x + (box_w - text_w) // 2
    elif spec.alignment == "right":
        anchor_x = box_x + (box_w - text_w)
    else:
        anchor_x = box_x
    anchor_y = box_y + (box_h - text_h) // 2

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))

    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    line_step = int(line_h * (1 + line_spacing))

    def _line_x(line: str) -> int:
        line_w = int(font.getlength(line))
        if spec.alignment == "center":
            return box_x + (box_w - line_w) // 2
        if spec.alignment == "right":
            return box_x + (box_w - line_w)
        return box_x

    scrim_shape = "halo"
    scrim_color = spec.scrim_color
    scrim_opacity = spec.scrim_opacity
    if template is not None and template.typography.scrim is not None:
        scrim_shape = template.typography.scrim.shape
        if template.typography.scrim.color:
            scrim_color = template.typography.scrim.color
        scrim_opacity = template.typography.scrim.opacity

    needs_scrim = spec.needs_scrim or (
        template is not None and template.typography.scrim and scrim_opacity > 0.0
    )

    if needs_scrim and scrim_opacity > 0.0:
        scrim_rgb = _hex_to_rgb(scrim_color)

        if scrim_shape == "full-band" and template is not None and "headline" in template.regions:
            r = template.regions["headline"]
            band = (
                int(r.x * W),
                int(r.y * H),
                int((r.x + r.w) * W),
                int((r.y + r.h) * H),
            )
            band_alpha = int(round(scrim_opacity * 255))
            band_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
            ImageDraw.Draw(band_layer).rectangle(band, fill=(*scrim_rgb, band_alpha))
            overlay = Image.alpha_composite(overlay, band_layer)

        elif scrim_shape == "rounded-block":
            pad_x = max(12, int(0.02 * W))
            pad_y = max(10, int(0.015 * H))
            rect = (
                _line_x(min(lines, key=lambda l: -font.getlength(l))) - pad_x,
                anchor_y - pad_y,
                box_x + box_w + pad_x,
                anchor_y + (line_step * len(lines)) + pad_y,
            )
            block = Image.new("RGBA", base.size, (0, 0, 0, 0))
            radius = max(8, int(0.014 * H))
            ImageDraw.Draw(block).rounded_rectangle(
                rect, radius=radius, fill=(*scrim_rgb, int(round(scrim_opacity * 255)))
            )
            overlay = Image.alpha_composite(overlay, block)

        else:
            mask = Image.new("L", base.size, 0)
            mdraw = ImageDraw.Draw(mask)
            for i, line in enumerate(lines):
                mdraw.text((_line_x(line), anchor_y + i * line_step), line, font=font, fill=255)
            dilate_size = max(3, int(initial_size * 0.05) | 1)
            mask = mask.filter(ImageFilter.MaxFilter(size=dilate_size))
            blur_radius = max(8, int(initial_size * 0.45))
            mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            opacity = max(0.0, min(1.0, scrim_opacity))
            alpha = mask.point(lambda v, o=opacity: int(v * o))
            halo = Image.new("RGBA", base.size, (*scrim_rgb, 0))
            halo.putalpha(alpha)
            overlay = Image.alpha_composite(overlay, halo)

    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    shadow_offset = max(1, int(0.0015 * H))
    shadow_text_color = (0, 0, 0, 110)
    for i, line in enumerate(lines):
        ly = anchor_y + i * line_step
        sdraw.text(
            (_line_x(line) + shadow_offset, ly + shadow_offset),
            line,
            font=font,
            fill=shadow_text_color,
        )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1, int(0.002 * H))))
    overlay = Image.alpha_composite(overlay, shadow)

    text_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_layer)
    text_rgb = _hex_to_rgb(spec.text_color)
    for i, line in enumerate(lines):
        ly = anchor_y + i * line_step
        tdraw.text((_line_x(line), ly), line, font=font, fill=(*text_rgb, 255))

    overlay = Image.alpha_composite(overlay, text_layer)
    return Image.alpha_composite(base, overlay).convert("RGB")
