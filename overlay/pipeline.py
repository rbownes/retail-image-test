"""Event-driven orchestration of the generate → critique → place → render pipeline.

`iterate_events` is a generator that yields typed events through every stage of
producing one finished creative. The CLI consumes it for stderr logging; the
web backend consumes it for SSE streaming.

Events carry native Python objects (PIL Images, Pydantic models) — base64
encoding for the wire is the network boundary's concern, not this module's.
"""

from __future__ import annotations

from typing import Any, Iterator, Literal, Protocol

from PIL import Image

from overlay import usage as usage_mod
from overlay.critique import ImageCritique, critique_image
from overlay.generate import generate_image
from overlay.placement import PlacementSpec, decide_placement
from overlay.render import render_overlay
from overlay.templates import Template


class CancelToken(Protocol):
    """Minimal interface a caller can use to stop iteration between stages."""

    def is_set(self) -> bool: ...


Event = dict[str, Any]
Stage = Literal["gen", "critique", "placement", "render"]


def _bumpseed(seed: int | None, i: int) -> int | None:
    if seed is None:
        return None
    return seed + i * 7919


def iterate_events(
    *,
    prompt: str,
    copy: str,
    template: Template | None = None,
    copy_zone: str | None = None,
    provider: str = "local",
    model: str | None = None,
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    steps: int = 4,
    quality: str = "medium",
    max_iterations: int = 5,
    font_path: str | None = None,
    cost_cap_usd: float | None = None,
    cancel: CancelToken | None = None,
) -> Iterator[Event]:
    """Drive the full pipeline, yielding one event per stage transition.

    Events emitted (terminal events end the stream):
      - gen_start             {iteration, max, prompt}
      - gen_done              {iteration, image, cost_so_far}
      - critique_start        {iteration}
      - critique_done         {iteration, critique, cost_so_far}
      - critique_failed       {iteration, message}            ← graceful, accepts current image
      - max_iterations_reached {iteration, warning}           ← only when cap reached without acceptance
      - placement_start       {}
      - placement_done        {spec, image, cost_so_far}
      - render_done           {final, raw, spec, critiques, final_prompt, total_cost}     ← terminal (success)
      - cost_cap_hit          {iteration, cost_so_far, cap}                                ← terminal
      - cancelled             {iteration}                                                  ← terminal
      - error                 {stage, message, exception_type}                             ← terminal
    """

    if copy_zone is None and template is not None:
        copy_zone = template.copy_zone

    current_prompt = prompt
    image: Image.Image | None = None
    critiques: list[ImageCritique] = []
    max_iter_warning: str | None = None

    def _cancelled() -> bool:
        return cancel is not None and cancel.is_set()

    def _over_cap() -> bool:
        return cost_cap_usd is not None and usage_mod.total_cost() >= cost_cap_usd

    try:
        for i in range(max_iterations):
            if _cancelled():
                yield {"type": "cancelled", "iteration": i}
                return
            if _over_cap():
                yield {
                    "type": "cost_cap_hit",
                    "iteration": i,
                    "cost_so_far": usage_mod.total_cost(),
                    "cap": cost_cap_usd,
                }
                return

            yield {
                "type": "gen_start",
                "iteration": i + 1,
                "max": max_iterations,
                "prompt": current_prompt,
            }
            image = generate_image(
                prompt=current_prompt,
                provider=provider,
                width=width,
                height=height,
                seed=_bumpseed(seed, i),
                model=model,
                steps=steps,
                quality=quality,
                label=f"image-gen-{i + 1}",
                copy_zone=copy_zone,
                template_directive=template.gen_directive if template else None,
            )
            yield {
                "type": "gen_done",
                "iteration": i + 1,
                "image": image,
                "cost_so_far": usage_mod.total_cost(),
            }

            is_last_iteration = max_iterations <= 1 or i == max_iterations - 1
            if is_last_iteration:
                if i + 1 == max_iterations and max_iterations > 1:
                    max_iter_warning = (
                        f"Reached iteration cap ({max_iterations}) without an acceptable critique — "
                        "the most recent image will be used. Review carefully before publishing."
                    )
                break

            yield {"type": "critique_start", "iteration": i + 1}
            try:
                critique = critique_image(image, current_prompt)
            except Exception as e:
                yield {
                    "type": "critique_failed",
                    "iteration": i + 1,
                    "message": f"{type(e).__name__}: {e}",
                }
                break

            critiques.append(critique)
            yield {
                "type": "critique_done",
                "iteration": i + 1,
                "critique": critique,
                "cost_so_far": usage_mod.total_cost(),
            }

            if critique.is_acceptable:
                break
            if not critique.refined_prompt:
                break

            current_prompt = critique.refined_prompt

        assert image is not None  # at least one generation always runs
        raw = image

        if _cancelled():
            yield {"type": "cancelled", "iteration": len(critiques)}
            return
        if _over_cap():
            yield {
                "type": "cost_cap_hit",
                "iteration": len(critiques),
                "cost_so_far": usage_mod.total_cost(),
                "cap": cost_cap_usd,
            }
            return

        if max_iter_warning is not None:
            yield {
                "type": "max_iterations_reached",
                "iteration": max_iterations,
                "warning": max_iter_warning,
            }

        template_region = None
        if template and "headline" in template.regions:
            r = template.regions["headline"]
            template_region = (r.x, r.y, r.w, r.h)

        yield {"type": "placement_start"}
        spec = decide_placement(
            image,
            copy,
            preferred_zone=copy_zone,
            template_hint=(template.placement_hint if template else None),
            template_region=template_region,
        )
        yield {
            "type": "placement_done",
            "spec": spec,
            "image": image,
            "cost_so_far": usage_mod.total_cost(),
        }

        final = render_overlay(image, copy, spec, font_path=font_path, template=template)
        yield {
            "type": "render_done",
            "final": final,
            "raw": raw,
            "spec": spec,
            "critiques": critiques,
            "final_prompt": current_prompt,
            "total_cost": usage_mod.total_cost(),
        }

    except Exception as e:
        stage: Stage
        # Best-effort stage attribution from the most recent event we'd have emitted.
        # Caller can use this to render contextual error UIs.
        stage = "render" if image is not None else "gen"
        yield {
            "type": "error",
            "stage": stage,
            "message": str(e),
            "exception_type": type(e).__name__,
        }


__all__ = ["iterate_events", "CancelToken", "Event"]
