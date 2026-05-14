from __future__ import annotations

from fastapi import APIRouter, HTTPException

from overlay.templates import list_templates, load_template

router = APIRouter(prefix="/api/templates", tags=["templates"])


def _serialize(t) -> dict:
    d = t.model_dump()
    if d.get("thumbnail"):
        d["thumbnail_url"] = f"/static/{d['thumbnail']}"
    return d


@router.get("")
def get_templates() -> list[dict]:
    return [_serialize(t) for t in list_templates()]


@router.get("/{template_id}")
def get_template(template_id: str) -> dict:
    try:
        return _serialize(load_template(template_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
