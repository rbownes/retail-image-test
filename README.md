# overlay

Generate an image with Stable Diffusion, then have Claude (vision) decide where to overlay a piece of copy so it doesn't cover the subject and reads cleanly.

## Setup

```bash
pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...
```

First run downloads SDXL-Turbo weights (~6.9 GB) into the HuggingFace cache.

## Usage

```bash
overlay --prompt "a serene mountain lake at dawn, cinematic" \
        --copy "Find your peace" \
        --out lake.png
```

### Options

| Flag | Default | Notes |
|---|---|---|
| `--prompt` | required | Image generation prompt |
| `--copy` | required | Text to overlay |
| `--out` | required | Output PNG path |
| `--font` | packaged Inter-Bold | Path to a TTF/OTF font |
| `--width` / `--height` | 1024 | Image dimensions |
| `--seed` | random | For reproducible image generation |
| `--model` | `stabilityai/sdxl-turbo` | Any diffusers text2image model id |
| `--steps` | 4 | Diffusion steps (turbo uses 1–4) |
| `--save-spec` | — | Dump the placement JSON for debugging |
| `--save-raw` | — | Save the pre-overlay image |

## How it works

1. **`generate.py`** — runs SDXL-Turbo locally via `diffusers` (MPS on Apple Silicon, CUDA, or CPU).
2. **`placement.py`** — sends the image + copy to Claude Opus 4.7 with vision; Claude returns a structured `PlacementSpec` (region, color, font size, alignment, scrim) via `messages.parse()` with a Pydantic schema.
3. **`render.py`** — Pillow draws the text with auto-fitting, word-wrap, optional scrim, and a subtle drop-shadow.
