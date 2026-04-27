from __future__ import annotations

from typing import Literal

import anthropic
from PIL import Image
from pydantic import BaseModel, Field

from overlay.placement import _image_to_b64_png
from overlay.usage import log_usage

_MODEL = "claude-opus-4-7"

_SYSTEM_PROMPT = """You are a senior art director reviewing a generated image for a marketing creative. Your only job is to catch *physically impossible* or *anatomically wrong* artifacts that the image generator produced — not to nitpick style or composition.

Look specifically for:
- People floating impossibly off the ground (no contact, no shadow alignment).
- Wrong number of limbs, fingers, or eyes; merged or contorted body parts.
- Broken physics (gravity, perspective, scale of objects, impossible reflections).
- Garbled text or impossible signage.
- Subjects awkwardly clipping into each other or the background.

Severity scale:
- "acceptable": no impossibilities; small style quirks are fine.
- "minor": one barely-noticeable artifact; can ship as-is.
- "moderate": one or two clear artifacts a casual viewer would spot.
- "severe": multiple obvious issues that break suspension of disbelief.

If severity is "acceptable" or "minor", set `is_acceptable: true` and `refined_prompt: null`. Otherwise, set `is_acceptable: false` and write a `refined_prompt` that:
- Keeps the *intent* of the original prompt (subject, mood, setting, copy-friendliness).
- Adds concrete language to fix the issues (e.g. "feet planted on the ground, weight on toes" if the runner was floating; "two visible runners, full bodies in frame" if anatomy was clipped).
- Stays under ~80 words. SDXL-Turbo doesn't support negative prompts — encode fixes positively.

Be decisive. Don't refine on minor stylistic differences."""


class ImageCritique(BaseModel):
    severity: Literal["acceptable", "minor", "moderate", "severe"]
    is_acceptable: bool
    issues: list[str] = Field(
        default_factory=list, description="Specific physical/anatomical artifacts found"
    )
    refined_prompt: str | None = Field(
        default=None, description="Rewritten prompt to fix the issues, or null if acceptable"
    )
    reasoning: str = ""


def critique_image(
    image: Image.Image,
    original_prompt: str,
    client: anthropic.Anthropic | None = None,
) -> ImageCritique:
    client = client or anthropic.Anthropic()
    b64 = _image_to_b64_png(image)

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
                            f"Original prompt:\n{original_prompt}\n\n"
                            "Review the image for physical impossibilities or anatomical errors."
                        ),
                    },
                ],
            }
        ],
        output_format=ImageCritique,
    )
    log_usage(_MODEL, response, "critique")

    critique = response.parsed_output
    if critique is None:
        raise RuntimeError(
            f"Claude did not return a valid ImageCritique (stop_reason={response.stop_reason})"
        )
    return critique
