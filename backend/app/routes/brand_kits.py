from __future__ import annotations

from fastapi import APIRouter, HTTPException

from overlay.brand_kits import list_brand_kits, load_brand_kit

router = APIRouter(prefix="/api/brand-kits", tags=["brand-kits"])


def _serialize(kit) -> dict:
    d = kit.model_dump()
    if d.get("logo"):
        d["logo_url"] = f"/static/{d['logo']}"
    return d


@router.get("")
def get_brand_kits() -> list[dict]:
    return [_serialize(k) for k in list_brand_kits()]


@router.get("/{brand_kit_id}")
def get_brand_kit(brand_kit_id: str) -> dict:
    try:
        return _serialize(load_brand_kit(brand_kit_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
