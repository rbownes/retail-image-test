from __future__ import annotations

import base64
import io
import re
from typing import Literal

import anthropic
from PIL import Image
from pydantic import BaseModel, Field, field_validator

from overlay.usage import log_usage

_MODEL = "claude-opus-4-7"

_SYSTEM_PROMPT = """You are a graphic designer placing a piece of marketing copy onto a generated image.

For the image and copy provided, decide:

1. **Region** — a rectangle (normalized 0-1 coords, origin top-left) where the text should be drawn. The region must:
   - Avoid the visual subject and any salient features (faces, focal objects, hands, signage).
   - Sit on a relatively uniform area so the text reads cleanly.
   - Leave at least 5% margin from every edge of the image.
   - Be wide and tall enough to comfortably fit the copy at the chosen font size — width should be at least 40% of the image, height proportional to copy length.

2. **Font size** — as a percentage of the image height. Headlines (≤6 words) typically 7-12%. Longer copy 4-7%. Never exceed 14%.

3. **Text color** — hex (#RRGGBB) chosen for maximum contrast against the chosen region. Pure white (#FFFFFF) and near-black (#0A0A0A) are usually right; brand colors only if the region is genuinely neutral.

4. **Alignment** — "left", "center", or "right" — match the visual weight of the image.

5. **Scrim** — only set `needs_scrim: true` if the chosen region's background is busy or low-contrast enough that the text would be hard to read. Prefer finding a clean region over relying on a scrim. If you do use one, `scrim_color` should be black for light text, white for dark text, and `scrim_opacity` between 0.3 and 0.6.

6. **Reasoning** — one sentence explaining why this region works.

Think carefully about composition before answering. Compositional rule of thumb: text reads best in the upper-third or lower-third on a calm area, aligned with the image's existing visual axis."""


class PlacementSpec(BaseModel):
    region: tuple[float, float, float, float] = Field(
        description="(x, y, width, height) normalized to [0, 1], origin top-left"
    )
    text_color: str = Field(description="Hex color #RRGGBB")
    font_size_pct: float = Field(ge=2.0, le=14.0, description="% of image height")
    alignment: Literal["left", "center", "right"]
    needs_scrim: bool
    scrim_color: str = Field(default="#000000", description="Hex color #RRGGBB")
    scrim_opacity: float = Field(ge=0.0, le=1.0, default=0.4)
    reasoning: str = ""

    @field_validator("region")
    @classmethod
    def _check_region(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x, y, w, h = v
        for name, val in (("x", x), ("y", y), ("w", w), ("h", h)):
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"region.{name}={val} must be in [0, 1]")
        if x + w > 1.0 + 1e-6 or y + h > 1.0 + 1e-6:
            raise ValueError(f"region {v} extends past image bounds")
        if w < 0.1 or h < 0.04:
            raise ValueError(f"region {v} is too small (w>=0.1, h>=0.04 required)")
        return v

    @field_validator("text_color", "scrim_color")
    @classmethod
    def _check_hex(cls, v: str) -> str:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            raise ValueError(f"color {v!r} must be #RRGGBB")
        return v.upper()


def _image_to_b64_png(image: Image.Image, max_dim: int = 1568) -> str:
    img = image.convert("RGB")
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


_ZONE_HINTS = {
    "top": "The image was composed with reserved negative space in the upper ~25% — strongly prefer placing copy there if quality permits.",
    "bottom": "The image was composed with reserved negative space in the lower ~25% — strongly prefer placing copy there if quality permits.",
    "left": "The image was composed with reserved negative space along the left ~25% — strongly prefer placing copy there if quality permits.",
    "right": "The image was composed with reserved negative space along the right ~25% — strongly prefer placing copy there if quality permits.",
    "top-left": "The image was composed with reserved negative space in the upper-left quadrant — strongly prefer placing copy there if quality permits.",
    "top-right": "The image was composed with reserved negative space in the upper-right quadrant — strongly prefer placing copy there if quality permits.",
    "bottom-left": "The image was composed with reserved negative space in the lower-left quadrant — strongly prefer placing copy there if quality permits.",
    "bottom-right": "The image was composed with reserved negative space in the lower-right quadrant — strongly prefer placing copy there if quality permits.",
}


def decide_placement(
    image: Image.Image,
    copy: str,
    client: anthropic.Anthropic | None = None,
    preferred_zone: str | None = None,
) -> PlacementSpec:
    client = client or anthropic.Anthropic()
    b64 = _image_to_b64_png(image)
    zone_hint = _ZONE_HINTS.get(preferred_zone or "", "")

    response = client.messages.parse(
        model=_MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Copy to overlay:\n\n{copy}\n\n"
                            f"Image dimensions: {image.width}x{image.height} px."
                            + (f"\n\n{zone_hint}" if zone_hint else "")
                        ),
                    },
                ],
            }
        ],
        output_format=PlacementSpec,
    )

    log_usage(_MODEL, response, "placement")

    spec = response.parsed_output
    if spec is None:
        raise RuntimeError(
            f"Claude did not return a valid PlacementSpec (stop_reason={response.stop_reason})"
        )
    return spec
