"""Batch-run a list of campaign scenarios through the overlay pipeline.

Usage:
    .venv/bin/python scripts/run_scenarios.py
    .venv/bin/python scripts/run_scenarios.py --provider local --max-iterations 1
    .venv/bin/python scripts/run_scenarios.py --only back-to-school,mothers-day
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from overlay import usage as usage_mod
from overlay.compose import composite_logo, composite_lockup
from overlay.critique import critique_image
from overlay.generate import generate_image
from overlay.placement import decide_placement
from overlay.render import render_overlay
from overlay.templates import load_template


def _run_one(
    scenario: dict,
    out_root: Path,
    *,
    provider: str,
    quality: str,
    width: int,
    height: int,
    max_iterations: int,
    reuse_raw: bool = False,
) -> dict:
    sid = scenario["id"]
    theme = scenario["theme"]
    prompt = scenario["prompt"]
    copy = scenario["copy"]
    copy_zone = scenario.get("copy_zone")
    template_id = scenario.get("template")
    template = load_template(template_id) if template_id else None
    out_dir = out_root / sid
    out_dir.mkdir(parents=True, exist_ok=True)

    if template is not None:
        copy_zone = copy_zone or template.copy_zone

    print(f"\n=== {theme} ({sid}) ===")
    print(f"copy: {copy!r}  template: {template_id or '(none)'}  zone: {copy_zone or '(none)'}")

    started = time.time()
    image = None
    final_prompt = prompt
    iterations_used = 0

    raw_path = out_dir / "raw.png"
    if reuse_raw and raw_path.exists():
        print(f"  [reuse] loading existing raw.png (skipping generation + critique)")
        from PIL import Image as _Image
        image = _Image.open(raw_path).convert("RGB")
        iterations_used = 0
    else:
        for i in range(max_iterations):
            iterations_used = i + 1
            print(f"  [gen {i + 1}/{max_iterations}] via {provider}")
            try:
                image = generate_image(
                    prompt=final_prompt,
                    provider=provider,
                    width=width,
                    height=height,
                    quality=quality,
                    label=f"{sid}-gen-{i + 1}",
                    copy_zone=copy_zone,
                    template_directive=template.gen_directive if template else None,
                )
            except Exception as e:
                print(f"    !! generation failed: {type(e).__name__}: {e}")
                return {
                    "id": sid,
                    "ok": False,
                    "stage": "generate",
                    "error": str(e),
                    "elapsed": time.time() - started,
                }

            image.save(out_dir / f"iter-{i + 1:02d}.png")

            if max_iterations <= 1 or i == max_iterations - 1:
                break

            print(f"  [critique {i + 1}]")
            try:
                critique = critique_image(image, final_prompt)
            except Exception as e:
                print(f"    !! critique failed: {type(e).__name__}: {e}; accepting current image")
                break

            (out_dir / f"iter-{i + 1:02d}-critique.json").write_text(
                json.dumps(critique.model_dump(), indent=2)
            )
            print(f"    severity={critique.severity}  acceptable={critique.is_acceptable}")
            if critique.issues:
                for issue in critique.issues:
                    print(f"      - {issue}")

            if critique.is_acceptable or not critique.refined_prompt:
                break

            print(f"    refined prompt: {critique.refined_prompt}")
            final_prompt = critique.refined_prompt

        image.save(out_dir / "raw.png")

    has_lockup = bool(scenario.get("lockup"))
    spec = None
    if not has_lockup:
        print("  [place]")
        template_region = None
        if template and "headline" in template.regions:
            r = template.regions["headline"]
            template_region = (r.x, r.y, r.w, r.h)
        try:
            spec = decide_placement(
                image,
                copy,
                preferred_zone=copy_zone,
                template_hint=(template.placement_hint if template else None),
                template_region=template_region,
            )
        except Exception as e:
            print(f"    !! placement failed: {type(e).__name__}: {e}")
            return {
                "id": sid,
                "ok": False,
                "stage": "place",
                "error": str(e),
                "elapsed": time.time() - started,
            }
        (out_dir / "spec.json").write_text(json.dumps(spec.model_dump(), indent=2))
        print(
            f"    region={spec.region} color={spec.text_color} "
            f"size={spec.font_size_pct:.1f}% align={spec.alignment} scrim={spec.needs_scrim}"
        )

    lockup_cfg = scenario.get("lockup")
    logo_cfg = scenario.get("logo")

    if lockup_cfg:
        # When a lockup is supplied we skip the headline overlay — the lockup IS the headline.
        print(f"  [compose] lockup -> {lockup_cfg.get('file')}")
        final = composite_lockup(
            image,
            lockup_cfg["file"],
            lockup_cfg["region"],
            align=lockup_cfg.get("align", "center"),
            tint=lockup_cfg.get("tint"),
        )
    else:
        print("  [render]")
        final = render_overlay(image, copy, spec, template=template)

    if logo_cfg:
        print(f"  [compose] logo   -> {logo_cfg.get('file')}")
        final = composite_logo(
            final,
            logo_cfg["file"],
            logo_cfg["region"],
            align=logo_cfg.get("align", "center"),
            tint=logo_cfg.get("tint"),
        )

    final_path = out_dir / "final.png"
    final.convert("RGB").save(final_path)
    print(f"  done -> {final_path}")

    return {
        "id": sid,
        "ok": True,
        "iterations": iterations_used,
        "final_prompt": final_prompt,
        "out": str(final_path),
        "elapsed": time.time() - started,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default="scenarios/retailer-campaigns.json", type=Path)
    ap.add_argument("--out", default="out/scenarios", type=Path)
    ap.add_argument("--provider", default="openai", choices=("local", "openai"))
    ap.add_argument("--quality", default="medium", choices=("low", "medium", "high", "auto"))
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--max-iterations", type=int, default=2)
    ap.add_argument("--only", default=None, help="comma-separated scenario ids")
    ap.add_argument(
        "--reuse-raw",
        action="store_true",
        help="If a scenario's out_dir already has raw.png, skip generation and critique and just re-run placement + composition. Free.",
    )
    args = ap.parse_args()

    scenarios = json.loads(args.scenarios.read_text())
    if args.only:
        keep = {x.strip() for x in args.only.split(",") if x.strip()}
        scenarios = [s for s in scenarios if s["id"] in keep]
        if not scenarios:
            print(f"no scenarios matched --only={args.only!r}", file=sys.stderr)
            return 1

    args.out.mkdir(parents=True, exist_ok=True)
    usage_mod.reset()

    print(f"running {len(scenarios)} scenario(s) via provider={args.provider}")
    print(f"output dir: {args.out}")

    started_all = time.time()
    results: list[dict] = []
    for s in scenarios:
        try:
            r = _run_one(
                s,
                args.out,
                provider=args.provider,
                quality=args.quality,
                width=args.width,
                height=args.height,
                max_iterations=args.max_iterations,
                reuse_raw=args.reuse_raw,
            )
        except KeyboardInterrupt:
            print("\ninterrupted; stopping batch", file=sys.stderr)
            break
        except Exception as e:
            traceback.print_exc()
            r = {"id": s["id"], "ok": False, "stage": "unhandled", "error": str(e)}
        results.append(r)

    elapsed = time.time() - started_all

    print("\n========== SUMMARY ==========")
    for r in results:
        sid = r["id"]
        if r.get("ok"):
            print(f"  [OK  ] {sid:<22} iters={r['iterations']} {r['elapsed']:5.1f}s -> {r['out']}")
        else:
            print(f"  [FAIL] {sid:<22} stage={r.get('stage')} error={r.get('error')}")
    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok_count}/{len(results)} scenarios succeeded in {elapsed:.1f}s")
    print(f"total estimated cost: ${usage_mod.total_cost():.4f}")
    print("\nper-call breakdown:")
    for line in usage_mod.summary_lines():
        print(line)

    summary_path = args.out / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "elapsed_seconds": elapsed,
                "total_cost_usd": usage_mod.total_cost(),
                "results": results,
                "usage_log": usage_mod.USAGE_LOG,
            },
            indent=2,
        )
    )
    print(f"\nsummary written -> {summary_path}")
    return 0 if ok_count == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
