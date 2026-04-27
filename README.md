# overlay

Agentic campaign-image generator. Produces a finished retail creative from one prompt and one piece of copy:

1. **Generate** an image (local Stable Diffusion **or** OpenAI `gpt-image-1`).
2. **Critique** it with Claude Opus 4.7 vision — flag anatomical/physical errors, rewrite the prompt, and regenerate up to N times.
3. **Place** the copy with Claude Opus 4.7 — pick a region, color, size, alignment, and scrim that don't fight the subject.
4. **Render** with Pillow — text-shape halo or full-width slab, drop-shadow, auto-wrap.

A library of **brand-style layout templates** ships with the project (Sports Direct-style value slab, Flannels-style editorial hush, USC-style streetwear stack, athletic diagonal). Each template injects composition directives into the generator and pins the placement agent to a known region with a known type/scrim treatment — so every output in a campaign feels like the same campaign.

## Setup

```bash
uv venv --python 3.13 .venv          # or python -m venv .venv
uv pip install --python .venv/bin/python -e .

export ANTHROPIC_API_KEY=sk-ant-...   # required (placement + critique agents)
export OPENAI_API_KEY=sk-proj-...     # required only if --provider openai
```

First local run downloads SDXL-Turbo weights (~6.9 GB) into the HuggingFace cache. Subsequent runs are ~30s on Apple Silicon (MPS).

## Quick start (one creative)

```bash
.venv/bin/python -m overlay \
  --provider openai --quality medium \
  --template value-slab \
  --max-iterations 2 \
  --prompt "Dramatic studio shot of premium retail products partially emerging from glossy black gift boxes, deep crimson and electric red rim lighting, true-black backdrop" \
  --copy "Up to 60% off everything" \
  --out out/black-friday.png
```

### CLI flags

| Flag | Default | Notes |
|---|---|---|
| `--prompt` | required | Image-generation prompt |
| `--copy` | required | Text to overlay |
| `--out` | required | Output PNG path |
| `--provider` | `local` | `local` (Stable Diffusion via diffusers) or `openai` (`gpt-image-1`) |
| `--model` | provider default | `stabilityai/sdxl-turbo` for local, `gpt-image-1` for openai |
| `--quality` | `medium` | OpenAI quality: `low` / `medium` / `high` / `auto` |
| `--steps` | 4 | Diffusion steps (local only) |
| `--width` / `--height` | 1024 | Output dimensions (snapped for OpenAI) |
| `--seed` | random | Reproducible local generation |
| `--max-iterations` | 5 | Critique loop cap; agent stops earlier if image is acceptable |
| `--template` | none | Brand layout: `value-slab`, `editorial-hush`, `streetwear-stack`, `athletic-diagonal` |
| `--copy-zone` | none | Manual reserved zone (`top` / `bottom` / `left` / `right` / corners) |
| `--font` | packaged Inter-Bold | Path to a TTF/OTF font |
| `--save-iterations` | — | Directory: dump every iteration's image and critique |
| `--save-spec` | — | Dump the placement spec JSON |
| `--save-raw` | — | Save the pre-overlay image |

## Batch mode (campaign scenarios)

Drop a JSON list of scenarios into [scenarios/](scenarios/). Each row needs `id`, `theme`, `template`, `prompt`, `copy`. Run:

```bash
.venv/bin/python scripts/run_scenarios.py \
  --provider openai --quality medium --max-iterations 2 \
  --out out/scenarios
```

Outputs land in `out/scenarios/<id>/` (`raw.png`, `final.png`, `spec.json`, per-iteration images and critiques) plus a top-level `summary.json` with full per-call usage and total cost.

The shipped [scenarios/retailer-campaigns.json](scenarios/retailer-campaigns.json) covers ten Frasers Group-style campaigns (Back to School, Black Friday, Holiday Gifting, Spring Fashion, Summer Essentials, Athleisure, Home Refresh, Beauty, Mother's Day, Sustainability), each mapped to one of the four brand templates.

## Templates

Templates live in [overlay/templates/](overlay/templates/) as JSON. Each defines:

- `regions` — normalized (0–1) rects for `subject`, `headline`, `wordmark`, `accent`
- `gen_directive` — text appended to the gen prompt to bake composition rules into the image
- `placement_hint` — instruction passed to Claude with the headline rect as a hard hint
- `typography` — alignment, font-size %, color, and **scrim shape**: `halo` (text-shape glow), `full-band` (solid color band), `rounded-block` (legacy rectangle)

| Template | Brand vibe | Subject | Copy region | Scrim |
|---|---|---|---|---|
| `value-slab` | Sports Direct, Lonsdale, Studio | Center-right, bleeding | Full-width bottom band | Solid navy `full-band` |
| `editorial-hush` | Flannels, Frasers, HoF premium | Vertical center, lots of empty space | Small bottom-right | None |
| `streetwear-stack` | USC, Jack Wills youth, FIRETRAP | Middle row, knee-cropped | Stacked upper-left | Light halo |
| `athletic-diagonal` | Slazenger, Karrimor, Everlast | Diagonal bottom-left → top-right | Bottom-left, all-caps | Moderate halo |

Add a new template by dropping `overlay/templates/<id>.json` (Pydantic-validated on load) — no code changes needed.

## Costs

Per run, with Opus 4.7 placement + critique:

| Stage | Tokens / unit | Cost |
|---|---|---|
| Placement | ~2.7K in / ~150 out | ~$0.018 |
| Critique (each iteration) | ~2.7K in / ~150 out | ~$0.018 |
| Image gen — local SDXL-Turbo | — | $0 |
| Image gen — `gpt-image-1` medium 1024² | flat per image | ~$0.042 |

Worst case for one creative with `--max-iterations 5` on OpenAI: ~$0.30. Typical: ~$0.10. The pipeline tracks per-call usage and emits a summary at the end.

## How it works

```
prompt + copy + template
        │
        ▼
┌─────────────────┐  text directive    ┌────────────────┐
│  generate.py    │ ──────────────────▶│  SDXL  /  GPT  │
│  (provider sw)  │                    │  image-1       │
└────────┬────────┘                    └───────┬────────┘
         │                                     │
         │              image                  │
         ▼                                     │
┌─────────────────┐  Claude Opus 4.7   ┌──────▼──────────┐
│  critique.py    │ ──── vision ─────▶ │  ImageCritique  │
│  (loop ≤N)      │                    │  + refined      │
└────────┬────────┘                    │    prompt       │
   acceptable?                         └─────────────────┘
         │                                     │ no →
         │ yes                                 └─→ regenerate
         ▼
┌─────────────────┐  Claude Opus 4.7   ┌─────────────────┐
│  placement.py   │ ──── vision ─────▶ │  PlacementSpec  │
│  (template hint)│                    │  region, color, │
└────────┬────────┘                    │  size, scrim    │
         │                             └─────────────────┘
         ▼
┌─────────────────┐
│  render.py      │  Pillow: word-wrap, halo / full-band scrim, drop-shadow
└────────┬────────┘
         ▼
     final.png
```

## Project layout

```
overlay/
├── __init__.py        # public API
├── __main__.py        # python -m overlay → cli.main
├── cli.py             # argparse + orchestration
├── generate.py        # SD / OpenAI dispatch, prompt augmentation
├── critique.py        # Claude vision agent: ImageCritique
├── placement.py       # Claude vision agent: PlacementSpec
├── render.py          # Pillow rendering, scrim shapes
├── usage.py           # cross-call usage + cost log
├── fonts/             # packaged Inter-Bold.otf
└── templates/         # brand layout JSONs (Pydantic-loaded)

scenarios/             # batch JSON
scripts/
└── run_scenarios.py   # batch runner
```

## License

Inter font (`overlay/fonts/Inter-Bold.otf`) is distributed under the SIL Open Font License v1.1 — see https://rsms.me/inter/.
