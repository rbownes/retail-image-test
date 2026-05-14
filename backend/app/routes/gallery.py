from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.services.gallery import get_gallery_item, list_gallery

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


@router.get("")
def gallery() -> list[dict]:
    return list_gallery()


@router.get("/{scenario_id}")
def gallery_item(scenario_id: str) -> dict:
    item = get_gallery_item(scenario_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario {scenario_id!r}")
    return item
