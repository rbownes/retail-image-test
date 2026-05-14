# CanvasKit

**Brief to brand-ready creative in under a minute** — an agentic retail
creative platform for multi-brand groups. Pick a sub-brand, pick a layout,
write a one-line brief. The system generates an image, critiques it for
anatomy / composition / on-brand-ness, regenerates as needed, places the
copy intelligently, and returns a publish-ready PNG with full cost
accounting.

## What's in the box

* **Web app**: Gallery landing → brand kit selector → live generation with
  per-iteration preview → downloadable PNG + spec + zipped campaign bundles.
* **Campaign builder**: author multiple briefs, run them as one batch, get a
  side-by-side grid plus a single zip.
* **Brand kit library**: Sports Direct, Flannels, Frasers, USC — each a JSON
  with palette, fonts, default layout, and a tone-of-voice note the AI
  honours.
* **Layout library**: 4 production-ready templates (Value Promo, Premium
  Editorial, Streetwear Youth, Athletic Performance), each with composition
  directives baked into the generator and a known copy zone.
* **Cost-aware**: every job estimates spend before running, displays running
  cost while generating, and supports a hard USD cap that stops the loop
  cleanly.

## What it does

```
brief + brand kit + layout
        │
        ▼
   generate ──┐
        │     │   not on-brand?
        │     └────────────────┐
        ▼                      │
    critique ─── refined prompt┘
        │ on-brand
        ▼
    place copy
        │
        ▼
     render ── final.png + spec.json
```

Every step is observable in the UI — you see each iteration as the system
critiques it, and you can stop or regenerate at any point.

## Quick start — Docker (recommended for teammates)

The fastest way to share this with the team. Requires Docker Desktop only;
no Python, no Node, no `.venv` to manage.

```bash
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY and OPENAI_API_KEY

docker compose up --build
# open http://localhost:3000
```

First build pulls Python + Node base images and takes 3–5 minutes. Subsequent
runs start in seconds. Per-job artifacts persist in a docker-managed volume
(`canvaskit_jobs`).

To stop: `docker compose down`. To wipe per-job outputs: `docker compose down -v`.

## Quick start — local dev (Python + Node)

Requires Python 3.10+, Node 18+, an Anthropic API key, and (for the recommended
provider) an OpenAI API key.

```bash
# 1. Install Python deps + the backend
uv pip install --python .venv/bin/python -e ".[backend]"

# Optional: add local Stable Diffusion (~3 GB of torch/diffusers/transformers).
uv pip install --python .venv/bin/python -e ".[local]"

# 2. Install frontend deps
cd frontend && npm install && cd ..

# 3. Configure keys
cp backend/.env.example backend/.env
# edit backend/.env to add ANTHROPIC_API_KEY and OPENAI_API_KEY

# 4. Run the stack (two terminals)
.venv/bin/uvicorn backend.app.main:app --port 8000
cd frontend && npm run dev   # then open http://localhost:3000
```

Open <http://localhost:3000>. The gallery shows 10 finished campaign
creatives that were produced by the same pipeline (total cost ~$0.75). Click
**+ New creative** to make one yourself.

## Demo material

`out/scenarios/` ships with 10 finished campaign creatives across four
brand layouts: Back to School, Black Friday, Holiday Gifting, Spring Fashion,
Summer Essentials, Athleisure, Home Refresh, Beauty, Mother's Day, Sustainability.
These power the landing-page gallery — your stakeholders see polished
output the moment they load the page.

## Architecture

* `overlay/` — the Python pipeline (generate, critique, place, render).
  Importable as a library; runnable via `python -m overlay` for one-shot
  CLI use.
* `backend/` — FastAPI app wrapping the pipeline as a job-based HTTP API
  with Server-Sent Events for live progress. See
  [backend/README.md](backend/README.md).
* `frontend/` — Next.js 16 (App Router, TypeScript, Tailwind v4) UI. See
  [frontend/README.md](frontend/README.md).
* `brand_kits/` — drop-in JSON per sub-brand: palette, fonts, default layout.
* `overlay/templates/` — drop-in JSON per layout: composition directive,
  copy zone, typography rules.
* `assets/` — logos, lockups, brand fonts.

Adding a new sub-brand = one JSON in `brand_kits/`. Adding a new layout =
one JSON in `overlay/templates/`. No code changes.

## Portability notes

* **Docker images are slim**: backend ~250 MB (Pillow + FastAPI + Pydantic),
  frontend ~150 MB (Next.js standalone). Total under 500 MB.
* **OpenAI-only by default**: the docker image does not bundle PyTorch
  (`overlay/generate.py` lazy-imports it). Local Stable Diffusion still works
  for native installs via `pip install -e ".[local]"`.
* **No external state**: in-memory job store. Restarting the backend container
  loses in-flight jobs but keeps completed artifacts (volume-mounted).
* **Single-machine**: this is a laptop / on-prem demo setup. To deploy for
  many users, swap the in-memory store for Redis, put auth in front, and
  bump compose to a real orchestrator.

## Costs

The UI shows an estimate before every run and tracks running cost during.
Typical per-image cost on `gpt-image-1` medium + Claude Opus 4.7:

| Stage | Cost |
|---|---|
| Image generation (one iteration) | ~$0.042 |
| Critique (per iteration after the first) | ~$0.018 |
| Placement | ~$0.018 |

A typical single creative lands around **$0.08**; a 5-iteration worst case
around **$0.30**. Set a hard cap in the UI to guarantee it.

## CLI (for developers)

The original CLI still works for one-shot scripted use:

```bash
.venv/bin/python -m overlay \
  --provider openai --quality medium \
  --template value-slab \
  --max-iterations 2 \
  --prompt "Dramatic studio shot of premium retail products..." \
  --copy "Up to 60% off everything" \
  --out out/black-friday.png
```

See `python -m overlay --help` for all flags. Batch CLI:
`python scripts/run_scenarios.py --provider openai`.

## License

Inter font (`overlay/fonts/Inter-Bold.otf`) is distributed under the SIL
Open Font License v1.1 — see <https://rsms.me/inter/>.
