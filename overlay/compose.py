"""Composite branded PNG assets (lockups, logos) onto a generated image.

A *lockup* is a pre-made title card / headline graphic (e.g. SIX NATIONS 2026 /
RUGBY STARTS HERE). A *logo* is a small brand chip (e.g. the Sports Direct
red+blue stacked mark).

Both are pasted with alpha over the generated image. Positions are normalized
(0-1) on the target canvas and the asset is scaled to *contain* its target rect
while preserving its aspect ratio.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"


def _resolve(asset_kind: str, name: str) -> Path:
    """Resolve an asset filename under assets/<kind>/, accepting absolute paths too."""
    p = Path(name)
    if p.is_absolute() and p.exists():
        return p
    candidate = ASSETS_ROOT / asset_kind / name
    if candidate.exists():
        return candidate
    # try with .png suffix
    if (candidate.with_suffix(".png")).exists():
        return candidate.with_suffix(".png")
    raise FileNotFoundError(
        f"asset not found: {name!r} under assets/{asset_kind}/. "
        f"Available: {sorted(p.name for p in (ASSETS_ROOT / asset_kind).glob('*'))}"
    )


def _fit_contain(asset: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """Scale asset to fit inside (box_w, box_h) preserving aspect ratio."""
    aw, ah = asset.size
    scale = min(box_w / aw, box_h / ah)
    new_size = (max(1, int(aw * scale)), max(1, int(ah * scale)))
    return asset.resize(new_size, Image.Resampling.LANCZOS)


def _normalize_region(region) -> tuple[float, float, float, float]:
    """Accept either (x,y,w,h) tuple/list or {x,y,w,h} dict."""
    if isinstance(region, dict):
        return (float(region["x"]), float(region["y"]), float(region["w"]), float(region["h"]))
    return tuple(float(v) for v in region)  # type: ignore[return-value]


def composite_asset(
    base: Image.Image,
    asset_path: str | Path,
    region,
    *,
    align: str = "center",
    tint_white_to: str | None = None,
) -> Image.Image:
    """Paste a transparent PNG onto base, fitted (contain) into a normalized region.

    region: (x, y, w, h) in [0, 1] — accepts a 4-tuple/list OR a dict with x/y/w/h
    keys. The asset is scaled to fit inside this rect while preserving aspect
    ratio, then aligned via `align` ('center', 'tl', 'tr', 'bl', 'br', 'tc',
    'bc', 'lc', 'rc').

    tint_white_to: if set (hex), recolors the white parts of the asset to this
    hex color. Useful for the SD outline lockups which ship as white-on-transparent.
    """
    base = base.convert("RGBA")
    W, H = base.size
    rx, ry, rw, rh = _normalize_region(region)
    box_x = int(rx * W)
    box_y = int(ry * H)
    box_w = max(1, int(rw * W))
    box_h = max(1, int(rh * H))

    asset = Image.open(asset_path).convert("RGBA")

    if tint_white_to:
        asset = _tint_to(asset, tint_white_to)

    asset = _fit_contain(asset, box_w, box_h)
    aw, ah = asset.size

    # alignment within the box
    a = align.lower()
    if a in ("center", "c"):
        ax = box_x + (box_w - aw) // 2
        ay = box_y + (box_h - ah) // 2
    elif a == "tl":
        ax, ay = box_x, box_y
    elif a == "tr":
        ax, ay = box_x + (box_w - aw), box_y
    elif a == "bl":
        ax, ay = box_x, box_y + (box_h - ah)
    elif a == "br":
        ax, ay = box_x + (box_w - aw), box_y + (box_h - ah)
    elif a == "tc":
        ax, ay = box_x + (box_w - aw) // 2, box_y
    elif a == "bc":
        ax, ay = box_x + (box_w - aw) // 2, box_y + (box_h - ah)
    elif a == "lc":
        ax, ay = box_x, box_y + (box_h - ah) // 2
    elif a == "rc":
        ax, ay = box_x + (box_w - aw), box_y + (box_h - ah) // 2
    else:
        ax = box_x + (box_w - aw) // 2
        ay = box_y + (box_h - ah) // 2

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.paste(asset, (ax, ay), asset)
    return Image.alpha_composite(base, layer)


def _tint_to(asset: Image.Image, hex_color: str) -> Image.Image:
    """Replace the RGB of fully-opaque pixels with hex_color, keep alpha as-is.

    Useful for the white-on-transparent SD lockups when overlaying on light
    backgrounds.
    """
    h = hex_color.lstrip("#")
    target = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    r, g, b, a = asset.split()
    solid = Image.new("RGBA", asset.size, (*target, 255))
    out = Image.composite(solid, Image.new("RGBA", asset.size, (0, 0, 0, 0)), a)
    return out


def composite_lockup(
    base: Image.Image,
    lockup_name: str,
    region,
    *,
    align: str = "center",
    tint: str | None = None,
) -> Image.Image:
    return composite_asset(
        base, _resolve("lockups", lockup_name), region, align=align, tint_white_to=tint
    )


def composite_logo(
    base: Image.Image,
    logo_name: str,
    region,
    *,
    align: str = "center",
    tint: str | None = None,
) -> Image.Image:
    return composite_asset(
        base, _resolve("logos", logo_name), region, align=align, tint_white_to=tint
    )


def list_lockups() -> list[str]:
    return sorted(p.name for p in (ASSETS_ROOT / "lockups").glob("*.png"))


def list_logos() -> list[str]:
    return sorted(p.name for p in (ASSETS_ROOT / "logos").glob("*.png"))
