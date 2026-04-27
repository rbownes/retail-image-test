from __future__ import annotations

import base64
import io
from typing import Literal

from PIL import Image

from overlay.usage import log_openai_image

Provider = Literal["local", "openai"]
Quality = Literal["low", "medium", "high", "auto"]
CopyZone = Literal["top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right"]


_ZONE_DIRECTIVES = {
    "top": "Compose with the subject in the lower 65% of the frame; leave the upper 25% as visually quiet, uniform negative space (soft gradient, sky, or simple background) suitable for a marketing headline overlay. No subject, faces, or busy detail in that band.",
    "bottom": "Compose with the subject in the upper 65% of the frame; leave the lower 25% as visually quiet, uniform negative space (clean ground, surface, or simple background) suitable for a marketing headline overlay. No subject, faces, or busy detail in that band.",
    "left": "Compose with the subject in the right 65% of the frame; leave the left 25% as visually quiet, uniform negative space suitable for a marketing headline overlay. No subject or busy detail in that band.",
    "right": "Compose with the subject in the left 65% of the frame; leave the right 25% as visually quiet, uniform negative space suitable for a marketing headline overlay. No subject or busy detail in that band.",
    "top-left": "Compose with the subject in the lower-right; leave the upper-left quadrant as visually quiet, uniform negative space for a marketing headline overlay.",
    "top-right": "Compose with the subject in the lower-left; leave the upper-right quadrant as visually quiet, uniform negative space for a marketing headline overlay.",
    "bottom-left": "Compose with the subject in the upper-right; leave the lower-left quadrant as visually quiet, uniform negative space for a marketing headline overlay.",
    "bottom-right": "Compose with the subject in the upper-left; leave the lower-right quadrant as visually quiet, uniform negative space for a marketing headline overlay.",
}


def _augment_prompt(prompt: str, copy_zone: CopyZone | None) -> str:
    if not copy_zone:
        return prompt
    directive = _ZONE_DIRECTIVES.get(copy_zone)
    if not directive:
        return prompt
    return f"{prompt}\n\nComposition note: {directive}"

_PIPELINE = None
_PIPELINE_KEY: tuple | None = None

_OPENAI_SIZES = [(1024, 1024), (1024, 1536), (1536, 1024)]


def _device_and_dtype():
    import torch

    if torch.backends.mps.is_available():
        return "mps", torch.float16
    if torch.cuda.is_available():
        return "cuda", torch.float16
    return "cpu", torch.float32


def _get_pipeline(model_id: str):
    global _PIPELINE, _PIPELINE_KEY
    from diffusers import AutoPipelineForText2Image

    device, dtype = _device_and_dtype()
    key = (model_id, device, str(dtype))
    if _PIPELINE is not None and _PIPELINE_KEY == key:
        return _PIPELINE

    pipe = AutoPipelineForText2Image.from_pretrained(
        model_id,
        torch_dtype=dtype,
        variant="fp16" if "float16" in str(dtype) else None,
    )
    pipe = pipe.to(device)
    pipe.set_progress_bar_config(disable=True)
    _PIPELINE = pipe
    _PIPELINE_KEY = key
    return pipe


def _generate_local(
    prompt: str,
    width: int,
    height: int,
    seed: int | None,
    model_id: str,
    steps: int,
) -> Image.Image:
    import torch

    pipe = _get_pipeline(model_id)

    generator = None
    if seed is not None:
        device, _ = _device_and_dtype()
        generator = torch.Generator(device="cpu" if device == "mps" else device).manual_seed(seed)

    is_turbo = "turbo" in model_id.lower()
    kwargs = dict(
        prompt=prompt,
        width=width,
        height=height,
        num_inference_steps=steps,
        generator=generator,
    )
    if is_turbo:
        kwargs["guidance_scale"] = 0.0

    return pipe(**kwargs).images[0]


def _snap_openai_size(width: int, height: int) -> str:
    target_ratio = width / height
    best = min(_OPENAI_SIZES, key=lambda s: abs(s[0] / s[1] - target_ratio))
    return f"{best[0]}x{best[1]}"


def _generate_openai(
    prompt: str,
    width: int,
    height: int,
    model: str,
    quality: Quality,
    label: str = "image-gen",
) -> Image.Image:
    from openai import OpenAI

    client = OpenAI()
    size = _snap_openai_size(width, height)

    response = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        quality=quality,
        n=1,
    )

    log_openai_image(model, response, label, quality=quality, size=size)

    b64 = response.data[0].b64_json
    if not b64:
        raise RuntimeError("OpenAI did not return image data (b64_json missing)")
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")

    if img.size != (width, height):
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    return img


def generate_image(
    prompt: str,
    *,
    provider: Provider = "local",
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    model: str | None = None,
    steps: int = 4,
    quality: Quality = "medium",
    label: str = "image-gen",
    copy_zone: CopyZone | None = None,
) -> Image.Image:
    augmented = _augment_prompt(prompt, copy_zone)
    if provider == "local":
        return _generate_local(
            prompt=augmented,
            width=width,
            height=height,
            seed=seed,
            model_id=model or "stabilityai/sdxl-turbo",
            steps=steps,
        )
    if provider == "openai":
        return _generate_openai(
            prompt=augmented,
            width=width,
            height=height,
            model=model or "gpt-image-1",
            quality=quality,
            label=label,
        )
    raise ValueError(f"unknown provider: {provider!r}")
