"""In-memory job store and pipeline runner.

Jobs run in a worker thread (via `asyncio.to_thread`). Events are pushed onto an
`asyncio.Queue` that the SSE endpoint drains. Each job owns a `UsageLog` so cost
accounting is isolated per job.

For laptop-only v1 this is a single-process `dict`; swap for Redis/RQ before
deploying.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from overlay import usage as usage_mod
from overlay.brand_kits import BrandKit, load_brand_kit
from overlay.pipeline import iterate_events
from overlay.templates import load_template
from overlay.usage import UsageLog, use_usage_log

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


# ----------------------------- request shape -----------------------------


@dataclass
class JobRequest:
    prompt: str
    copy: str
    brand_kit_id: Optional[str] = None
    template_id: Optional[str] = None
    provider: str = "openai"
    model: Optional[str] = None
    quality: str = "medium"
    width: int = 1024
    height: int = 1024
    seed: Optional[int] = None
    steps: int = 4
    max_iterations: int = 3
    copy_zone: Optional[str] = None
    cost_cap_usd: Optional[float] = None


# ----------------------------- job state ---------------------------------


@dataclass
class Job:
    id: str
    request: JobRequest
    status: str = "queued"  # queued | running | done | error | cancelled | cost_capped
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    usage: UsageLog = field(default_factory=UsageLog)
    queue: "asyncio.Queue[dict]" = field(default_factory=asyncio.Queue)
    cancel_flag: threading.Event = field(default_factory=threading.Event)
    final_path: Optional[Path] = None
    raw_path: Optional[Path] = None
    spec_path: Optional[Path] = None
    summary_path: Optional[Path] = None
    error: Optional[str] = None
    parent_id: Optional[str] = None
    child_ids: list[str] = field(default_factory=list)

    def output_dir(self) -> Path:
        return get_settings().jobs_dir / self.id

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "request": self.request.__dict__,
            "total_cost_usd": self.usage.total_cost(),
            "error": self.error,
            "final_url": _job_static_url(self.id, "final.png") if self.final_path else None,
            "raw_url": _job_static_url(self.id, "raw.png") if self.raw_path else None,
            "spec_url": _job_static_url(self.id, "spec.json") if self.spec_path else None,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
        }


def _job_static_url(job_id: str, filename: str) -> str:
    return f"/static/jobs/{job_id}/{filename}"


# --------------------------- in-memory store -----------------------------


_JOBS: dict[str, Job] = {}
_STORE_LOCK = threading.Lock()


def create_job(req: JobRequest, *, parent_id: str | None = None) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], request=req, parent_id=parent_id)
    with _STORE_LOCK:
        _JOBS[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return _JOBS.get(job_id)


def list_jobs() -> list[Job]:
    with _STORE_LOCK:
        return list(_JOBS.values())


# ---------------------------- pipeline runner ----------------------------


def _image_to_b64(img: Image.Image, max_dim: int = 1024) -> str:
    out = img.copy()
    out.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _push(queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, payload: dict) -> None:
    asyncio.run_coroutine_threadsafe(queue.put(payload), loop).result(timeout=5)


def _serialize_event(event: dict) -> dict:
    """Translate native pipeline events into JSON-safe dicts for the SSE wire."""
    kind = event["type"]
    out: dict[str, Any] = {"type": kind}
    for k, v in event.items():
        if k == "type":
            continue
        if isinstance(v, Image.Image):
            out[k + "_b64"] = _image_to_b64(v)
        elif hasattr(v, "model_dump"):
            out[k] = v.model_dump()
        elif isinstance(v, list) and v and hasattr(v[0], "model_dump"):
            out[k] = [item.model_dump() for item in v]
        else:
            out[k] = v
    return out


def _resolve_template(brand_kit: BrandKit | None, template_id: str | None):
    if template_id:
        return load_template(template_id)
    if brand_kit:
        return load_template(brand_kit.default_template)
    return None


def _run_pipeline_blocking(job: Job, loop: asyncio.AbstractEventLoop) -> None:
    settings = get_settings()
    out_dir = job.output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    job.status = "running"
    job.started_at = time.time()

    req = job.request

    try:
        brand_kit = load_brand_kit(req.brand_kit_id) if req.brand_kit_id else None
    except ValueError as e:
        job.status = "error"
        job.error = str(e)
        job.finished_at = time.time()
        _push(job.queue, loop, {"type": "error", "stage": "setup", "message": str(e), "exception_type": "ValueError"})
        _push(job.queue, loop, {"type": "__terminal__"})
        return

    template = _resolve_template(brand_kit, req.template_id)

    # Respect a per-process safety cap.
    cap = req.cost_cap_usd
    if cap is None or cap > settings.max_cost_usd_per_job:
        cap = settings.max_cost_usd_per_job

    final_image: Image.Image | None = None
    raw_image: Image.Image | None = None
    spec_payload: dict | None = None
    critiques_payload: list[dict] = []
    terminal = False

    with use_usage_log(job.usage):
        for event in iterate_events(
            prompt=req.prompt,
            copy=req.copy,
            template=template,
            copy_zone=req.copy_zone,
            provider=req.provider,
            model=req.model,
            width=req.width,
            height=req.height,
            seed=req.seed,
            steps=req.steps,
            quality=req.quality,
            max_iterations=req.max_iterations,
            cost_cap_usd=cap,
            cancel=job.cancel_flag,
        ):
            kind = event["type"]
            if kind == "gen_done":
                img = event["image"]
                img.save(out_dir / f"iter-{event['iteration']:02d}.png")
            elif kind == "critique_done":
                critiques_payload.append(event["critique"].model_dump())
            elif kind == "placement_done":
                raw_image = event["image"]
                spec_payload = event["spec"].model_dump()
                raw_image.save(out_dir / "raw.png")
                (out_dir / "spec.json").write_text(json.dumps(spec_payload, indent=2))
                job.raw_path = out_dir / "raw.png"
                job.spec_path = out_dir / "spec.json"
            elif kind == "render_done":
                final_image = event["final"]
                final_image.save(out_dir / "final.png")
                job.final_path = out_dir / "final.png"
            elif kind == "error":
                job.status = "error"
                job.error = event["message"]
                terminal = True
            elif kind == "cost_cap_hit":
                job.status = "cost_capped"
                terminal = True
            elif kind == "cancelled":
                job.status = "cancelled"
                terminal = True

            _push(job.queue, loop, _serialize_event(event))

            if terminal:
                break

    if not terminal and job.status == "running":
        job.status = "done"

    job.finished_at = time.time()

    summary = {
        "id": job.id,
        "status": job.status,
        "elapsed_seconds": (job.finished_at or 0) - (job.started_at or 0),
        "total_cost_usd": job.usage.total_cost(),
        "request": job.request.__dict__,
        "spec": spec_payload,
        "critiques": critiques_payload,
        "error": job.error,
        "usage_log": job.usage.entries,
    }
    job.summary_path = out_dir / "summary.json"
    job.summary_path.write_text(json.dumps(summary, indent=2))

    # Final state event so the SSE client can update its UI deterministically.
    _push(
        job.queue,
        loop,
        {
            "type": "job_finalized",
            "status": job.status,
            "total_cost": job.usage.total_cost(),
            "final_url": _job_static_url(job.id, "final.png") if job.final_path else None,
            "raw_url": _job_static_url(job.id, "raw.png") if job.raw_path else None,
            "spec_url": _job_static_url(job.id, "spec.json") if job.spec_path else None,
            "summary_url": _job_static_url(job.id, "summary.json"),
        },
    )
    _push(job.queue, loop, {"type": "__terminal__"})


async def run_job(job: Job) -> None:
    loop = asyncio.get_running_loop()
    try:
        await asyncio.to_thread(_run_pipeline_blocking, job, loop)
    except Exception as e:  # noqa: BLE001
        logger.exception("job %s crashed", job.id)
        job.status = "error"
        job.error = f"{type(e).__name__}: {e}"
        job.finished_at = time.time()
        await job.queue.put(
            {"type": "error", "stage": "runner", "message": str(e), "exception_type": type(e).__name__}
        )
        await job.queue.put({"type": "__terminal__"})


# --------------------------- batch coordinator ---------------------------


@dataclass
class BatchRequest:
    name: str
    briefs: list[JobRequest]


async def run_batch(parent_job: Job, briefs: list[JobRequest]) -> None:
    loop = asyncio.get_running_loop()
    parent_job.status = "running"
    parent_job.started_at = time.time()

    for idx, brief in enumerate(briefs):
        child = create_job(brief, parent_id=parent_job.id)
        parent_job.child_ids.append(child.id)
        await parent_job.queue.put(
            {"type": "child_queued", "child_id": child.id, "index": idx, "total": len(briefs)}
        )

        async def _forward(child_job: Job, child_idx: int) -> None:
            await asyncio.to_thread(_run_pipeline_blocking, child_job, loop)

        # Run sequentially (rate-limit safe); fan out child events to parent stream.
        forwarder_task = asyncio.create_task(_forward_child_events(child, parent_job))
        await _forward(child, idx)
        await forwarder_task

    parent_job.status = "done"
    parent_job.finished_at = time.time()
    await parent_job.queue.put({"type": "batch_done", "total": len(briefs)})
    await parent_job.queue.put({"type": "__terminal__"})


async def _forward_child_events(child: Job, parent: Job) -> None:
    while True:
        event = await child.queue.get()
        if event.get("type") == "__terminal__":
            await parent.queue.put({"type": "child_terminal", "child_id": child.id})
            return
        await parent.queue.put({"child_id": child.id, **event})


# --------------------------- batch bundle export -------------------------


def build_batch_bundle(parent: Job) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cid in parent.child_ids:
            child = get_job(cid)
            if not child:
                continue
            if child.final_path and child.final_path.exists():
                zf.write(child.final_path, arcname=f"{cid}/final.png")
            if child.raw_path and child.raw_path.exists():
                zf.write(child.raw_path, arcname=f"{cid}/raw.png")
            if child.spec_path and child.spec_path.exists():
                zf.write(child.spec_path, arcname=f"{cid}/spec.json")
            if child.summary_path and child.summary_path.exists():
                zf.write(child.summary_path, arcname=f"{cid}/summary.json")
        zf.writestr(
            "summary.json",
            json.dumps(
                {
                    "id": parent.id,
                    "status": parent.status,
                    "children": [get_job(cid).to_summary() for cid in parent.child_ids if get_job(cid)],
                    "total_cost_usd": sum(
                        get_job(cid).usage.total_cost()
                        for cid in parent.child_ids
                        if get_job(cid)
                    ),
                },
                indent=2,
            ),
        )
    return buf.getvalue()
