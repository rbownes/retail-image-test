from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from overlay import usage as usage_mod
from overlay.pipeline import iterate_events
from overlay.templates import load_template, template_ids


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
        "--template",
        choices=template_ids(),
        default=None,
        help="Brand layout template (overrides --copy-zone if set). Available: " + ", ".join(template_ids()),
    )
    p.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Max image-generation rounds; the agent critiques each and rewrites the prompt until acceptable. Set to 1 to skip critique.",
    )
    p.add_argument(
        "--cost-cap",
        type=float,
        default=None,
        help="Hard cost ceiling in USD; pipeline stops between iterations if exceeded.",
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


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    usage_mod.reset()

    template = load_template(args.template) if args.template else None
    iter_dir: Path | None = args.save_iterations
    if iter_dir is not None:
        iter_dir.mkdir(parents=True, exist_ok=True)

    final = None
    raw = None
    spec = None
    final_prompt = args.prompt
    exit_code = 0

    events = iterate_events(
        prompt=args.prompt,
        copy=args.copy,
        template=template,
        copy_zone=args.copy_zone,
        provider=args.provider,
        model=args.model,
        width=args.width,
        height=args.height,
        seed=args.seed,
        steps=args.steps,
        quality=args.quality,
        max_iterations=args.max_iterations,
        font_path=args.font,
        cost_cap_usd=args.cost_cap,
    )

    for event in events:
        kind = event["type"]
        if kind == "gen_start":
            print(
                f"[gen {event['iteration']}/{event['max']}] generating via {args.provider} ({args.width}x{args.height})...",
                file=sys.stderr,
            )
        elif kind == "gen_done":
            if iter_dir is not None:
                event["image"].save(iter_dir / f"iter-{event['iteration']:02d}.png")
        elif kind == "critique_start":
            print(f"[critique {event['iteration']}] reviewing for impossibilities...", file=sys.stderr)
        elif kind == "critique_done":
            c = event["critique"]
            print(
                f"           severity={c.severity} acceptable={c.is_acceptable} issues={c.issues}",
                file=sys.stderr,
            )
            if iter_dir is not None:
                (iter_dir / f"iter-{event['iteration']:02d}-critique.json").write_text(
                    json.dumps(c.model_dump(), indent=2)
                )
            if c.is_acceptable:
                print("           accepted — stopping iteration.", file=sys.stderr)
            elif not c.refined_prompt:
                print("           no refined prompt returned — stopping iteration.", file=sys.stderr)
            else:
                print(f"           refined prompt: {c.refined_prompt}", file=sys.stderr)
        elif kind == "critique_failed":
            print(
                f"           critique failed ({event['message']}); accepting current image.",
                file=sys.stderr,
            )
        elif kind == "max_iterations_reached":
            print(f"[warn] {event['warning']}", file=sys.stderr)
        elif kind == "placement_start":
            print("[place] asking Claude where to place the copy...", file=sys.stderr)
        elif kind == "placement_done":
            spec = event["spec"]
            raw = event["image"]
            if args.save_raw:
                args.save_raw.parent.mkdir(parents=True, exist_ok=True)
                raw.save(args.save_raw)
                print(f"           raw image -> {args.save_raw}", file=sys.stderr)
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
        elif kind == "render_done":
            final = event["final"]
            final_prompt = event["final_prompt"]
        elif kind == "cost_cap_hit":
            print(
                f"[stop] cost cap ${event['cap']:.4f} reached at ${event['cost_so_far']:.4f} after iteration {event['iteration']}.",
                file=sys.stderr,
            )
            exit_code = 2
        elif kind == "cancelled":
            print(f"[stop] cancelled at iteration {event['iteration']}.", file=sys.stderr)
            exit_code = 2
        elif kind == "error":
            print(
                f"[error] stage={event['stage']} {event['exception_type']}: {event['message']}",
                file=sys.stderr,
            )
            exit_code = 1

    if final is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        final.save(args.out)
        print(f"done -> {args.out}", file=sys.stderr)

    print("\n[usage]", file=sys.stderr)
    for line in usage_mod.summary_lines():
        print(line, file=sys.stderr)
    print(f"\nfinal prompt used: {final_prompt}", file=sys.stderr)
    return exit_code
