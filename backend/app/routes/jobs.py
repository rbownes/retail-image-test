from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services import jobs as jobs_svc
from backend.app.services.estimate import estimate_cost

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ----------------------------- request models ---------------------------


class SingleJobRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str
    copy_text: str = Field(alias="copy")
    brand_kit_id: str | None = None
    template_id: str | None = None
    provider: str = "openai"
    model: str | None = None
    quality: str = "medium"
    width: int = 1024
    height: int = 1024
    seed: int | None = None
    steps: int = 4
    max_iterations: int = Field(default=3, ge=1, le=8)
    copy_zone: str | None = None
    cost_cap_usd: float | None = None


class BatchJobRequest(BaseModel):
    name: str = "Untitled campaign"
    briefs: list[SingleJobRequest]


class EstimateRequest(BaseModel):
    provider: str = "openai"
    quality: str = "medium"
    max_iterations: int = 3


# ------------------------------ helpers ---------------------------------


def _to_job_request(payload: SingleJobRequest) -> jobs_svc.JobRequest:
    data = payload.model_dump(by_alias=False)
    data["copy"] = data.pop("copy_text")
    return jobs_svc.JobRequest(**data)


async def _sse_from_queue(queue: asyncio.Queue):
    """Yield text/event-stream lines from a job's event queue."""
    while True:
        event = await queue.get()
        if event.get("type") == "__terminal__":
            yield "event: terminal\ndata: {}\n\n"
            return
        yield f"data: {json.dumps(event, default=str)}\n\n"


# ----------------------------- endpoints --------------------------------


@router.post("/estimate")
def post_estimate(req: EstimateRequest) -> dict[str, Any]:
    return estimate_cost(req.model_dump())


@router.post("/single")
async def post_single(req: SingleJobRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    job = jobs_svc.create_job(_to_job_request(req))
    background_tasks.add_task(jobs_svc.run_job, job)
    return {"job_id": job.id}


@router.post("/batch")
async def post_batch(req: BatchJobRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    if not req.briefs:
        raise HTTPException(status_code=400, detail="at least one brief is required")
    # Parent job is a meta-job: status + queue, no pipeline.
    placeholder = jobs_svc.JobRequest(prompt=req.name, copy=req.name, max_iterations=1)
    parent = jobs_svc.create_job(placeholder)
    child_reqs = [_to_job_request(b) for b in req.briefs]
    background_tasks.add_task(jobs_svc.run_batch, parent, child_reqs)
    return {"job_id": parent.id, "expected_children": len(req.briefs)}


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = jobs_svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job")
    return job.to_summary()


@router.get("/{job_id}/events")
async def get_job_events(job_id: str):
    job = jobs_svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job")
    return StreamingResponse(_sse_from_queue(job.queue), media_type="text/event-stream")


@router.get("/{job_id}/batch-events")
async def get_batch_events(job_id: str):
    job = jobs_svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job")
    return StreamingResponse(_sse_from_queue(job.queue), media_type="text/event-stream")


@router.post("/{job_id}/cancel")
def post_cancel(job_id: str) -> dict[str, str]:
    job = jobs_svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job")
    job.cancel_flag.set()
    return {"status": "cancel_requested"}


@router.get("/{job_id}/download/{kind}")
def get_download(job_id: str, kind: str):
    job = jobs_svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job")
    if kind == "final" and job.final_path:
        return FileResponse(job.final_path, media_type="image/png", filename=f"{job_id}-final.png")
    if kind == "raw" and job.raw_path:
        return FileResponse(job.raw_path, media_type="image/png", filename=f"{job_id}-raw.png")
    if kind == "spec" and job.spec_path:
        return FileResponse(job.spec_path, media_type="application/json", filename=f"{job_id}-spec.json")
    if kind == "summary" and job.summary_path:
        return FileResponse(job.summary_path, media_type="application/json", filename=f"{job_id}-summary.json")
    if kind in ("bundle", "bundle.zip"):
        if not job.child_ids:
            raise HTTPException(status_code=400, detail="not a batch job")
        zip_bytes = jobs_svc.build_batch_bundle(job)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={job_id}-campaign.zip"},
        )
    raise HTTPException(status_code=404, detail=f"no {kind} for job {job_id}")
