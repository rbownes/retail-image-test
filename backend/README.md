# CanvasKit backend

FastAPI wrapper over the `overlay` Python pipeline. Drives the agentic
generate → critique → place → render loop and streams live progress to a
frontend over SSE.

## Run locally

```bash
# from the repo root
uv pip install --python .venv/bin/python -e ".[backend]"

cp backend/.env.example backend/.env   # fill in ANTHROPIC_API_KEY and OPENAI_API_KEY
set -a; source backend/.env; set +a

.venv/bin/uvicorn backend.app.main:app --reload --port 8000
```

Open <http://localhost:8000/docs> for the interactive API explorer.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + product metadata |
| GET | `/api/brand-kits` | All brand kits (logo URLs, palette, default template) |
| GET | `/api/templates` | All layout templates (display name + thumbnail URL) |
| GET | `/api/gallery` | The 10 finished scenarios under `out/scenarios/` |
| GET | `/api/gallery/{id}` | One gallery item (raw + final + spec) |
| POST | `/api/jobs/estimate` | Pre-run cost estimate `{min, expected, max}` |
| POST | `/api/jobs/single` | Kick off one creative — returns `{job_id}` |
| GET | `/api/jobs/{id}/events` | SSE stream of live pipeline events |
| GET | `/api/jobs/{id}` | Job summary (terminal state) |
| POST | `/api/jobs/{id}/cancel` | Stop a running job at the next iteration boundary |
| GET | `/api/jobs/{id}/download/{kind}` | Download `final` / `raw` / `spec` / `summary` / `bundle.zip` |
| POST | `/api/jobs/batch` | Kick off a campaign — returns parent `{job_id}` |
| GET | `/api/jobs/{id}/batch-events` | SSE merge of all child events tagged by `child_id` |

## SSE event shape

Events match `overlay/pipeline.py::iterate_events` with a network-friendly
encoding: `Image.Image` values become `<key>_b64` (base64 PNG, max 1024px),
Pydantic models become plain dicts.

Terminal events: `render_done` (success), `error`, `cost_cap_hit`, `cancelled`.
Each stream ends with a sentinel `event: terminal` line.

## Storage

* In-memory job store (single process, no persistence). Restart loses
  history. Swap for Redis before deploying.
* Each job writes `out/jobs/{id}/{final.png,raw.png,spec.json,summary.json}`
  plus per-iteration PNGs.
