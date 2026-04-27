from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

from overlay import usage as usage_mod
from overlay.critique import ImageCritique, critique_image
from overlay.generate import generate_image
from overlay.placement import decide_placement
from overlay.render import render_overlay


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="overlay",
        description="Generate an image, critique it agentically, then overlay copy in the best spot.",
    )
    p.add_argument("--prompt", required=True, help="Image generation prompt")
    p.add_argument("--copy", required=True, help="Text to overlay on the image")
    p.add_argument("--out", required=True, type=Path, help="Output PNG path")
    p.add_argument("--font", default=None, help="Path to a TTF/OTF font file")
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument(
        "--provider",
        choices=("local", "openai"),
        default="local",
        help="Image generator: 'local' = Stable Diffusion via diffusers (free, MPS/CUDA/CPU); 'openai' = gpt-image-1 (paid, no GPU needed).",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Model id. Default depends on --provider: local→'stabilityai/sdxl-turbo', openai→'gpt-image-1'.",
    )
    p.add_argument("--steps", type=int, default=4, help="Diffusion steps (local only)")
    p.add_argument(
        "--quality",
        choices=("low", "medium", "high", "auto"),
        default="medium",
        help="OpenAI image quality (openai provider only)",
    )
    p.add_argument(
        "--copy-zone",
        choices=(
            "top", "bottom", "left", "right",
            "top-left", "top-right", "bottom-left", "bottom-right",
        ),
        default=None,
        help="Reserve a quiet zone for copy: bias both the generator and the placement agent toward this region.",
    )
    p.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Max image-generation rounds; the agent critiques each and rewrites the prompt until acceptable. Set to 1 to skip critique.",
    )
    p.add_argument(
        "--save-spec",
        type=Path,
        default=None,
        help="Write the placement spec JSON here (debug)",
    )
    p.add_argument(
        "--save-raw",
        type=Path,
        default=None,
        help="Write the final pre-overlay image here (debug)",
    )
    p.add_argument(
        "--save-iterations",
        type=Path,
        default=None,
        help="Directory: save each iteration's image and critique JSON",
    )
    return p


def _bumpseed(seed: int | None, i: int) -> int | None:
    if seed is None:
        return None
    return seed + i * 7919


def _iterate(args) -> tuple[Image.Image, str, list[ImageCritique]]:
    prompt = args.prompt
    image: Image.Image | None = None
    critiques: list[ImageCritique] = []
    iter_dir: Path | None = args.save_iterations

    if iter_dir is not None:
        iter_dir.mkdir(parents=True, exist_ok=True)

    for i in range(args.max_iterations):
        print(
            f"[gen {i + 1}/{args.max_iterations}] generating via {args.provider} ({args.width}x{args.height})...",
            file=sys.stderr,
        )
        image = generate_image(
            prompt=prompt,
            provider=args.provider,
            width=args.width,
            height=args.height,
            seed=_bumpseed(args.seed, i),
            model=args.model,
            steps=args.steps,
            quality=args.quality,
            label=f"image-gen-{i + 1}",
            copy_zone=args.copy_zone,
        )

        if iter_dir is not None:
            image.save(iter_dir / f"iter-{i + 1:02d}.png")

        if args.max_iterations <= 1 or i == args.max_iterations - 1:
            return image, prompt, critiques

        print(f"[critique {i + 1}] reviewing for impossibilities...", file=sys.stderr)
        try:
            critique = critique_image(image, prompt)
        except Exception as e:
            print(f"           critique failed ({type(e).__name__}: {e}); accepting current image.", file=sys.stderr)
            return image, prompt, critiques
        critiques.append(critique)
        print(
            f"           severity={critique.severity} "
            f"acceptable={critique.is_acceptable} "
            f"issues={critique.issues}",
            file=sys.stderr,
        )

        if iter_dir is not None:
            (iter_dir / f"iter-{i + 1:02d}-critique.json").write_text(
                json.dumps(critique.model_dump(), indent=2)
            )

        if critique.is_acceptable:
            print("           accepted — stopping iteration.", file=sys.stderr)
            return image, prompt, critiques

        if not critique.refined_prompt:
            print("           no refined prompt returned — stopping iteration.", file=sys.stderr)
            return image, prompt, critiques

        print(f"           refined prompt: {critique.refined_prompt}", file=sys.stderr)
        prompt = critique.refined_prompt

    assert image is not None
    return image, prompt, critiques


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    usage_mod.reset()

    image, final_prompt, critiques = _iterate(args)

    if args.save_raw:
        args.save_raw.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.save_raw)
        print(f"           raw image -> {args.save_raw}", file=sys.stderr)

    print("[place] asking Claude where to place the copy...", file=sys.stderr)
    spec = decide_placement(image, args.copy, preferred_zone=args.copy_zone)
    print(
        f"        region={spec.region} color={spec.text_color} "
        f"size={spec.font_size_pct:.1f}% align={spec.alignment} scrim={spec.needs_scrim}",
        file=sys.stderr,
    )
    print(f"        reasoning: {spec.reasoning}", file=sys.stderr)
    if args.save_spec:
        args.save_spec.parent.mkdir(parents=True, exist_ok=True)
        args.save_spec.write_text(json.dumps(spec.model_dump(), indent=2))

    print("[render] drawing text overlay...", file=sys.stderr)
    final = render_overlay(image, args.copy, spec, font_path=args.font)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    final.save(args.out)
    print(f"done -> {args.out}", file=sys.stderr)

    print("\n[usage]", file=sys.stderr)
    for line in usage_mod.summary_lines():
        print(line, file=sys.stderr)
    print(
        f"\nfinal prompt used: {final_prompt}",
        file=sys.stderr,
    )
    return 0
