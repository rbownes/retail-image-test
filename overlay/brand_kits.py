from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

_BRAND_KITS_DIR = Path(__file__).resolve().parent.parent / "brand_kits"


class BrandKit(BaseModel):
    id: str
    name: str
    tagline: str = ""
    tone: str = ""
    primary: str = "#000000"
    secondary: str = "#FFFFFF"
    accent: str = "#000000"
    text_on_primary: str = "#FFFFFF"
    logo: str | None = None
    font_display: str | None = None
    font_body: str | None = None
    default_template: str = "value-slab"
    supported_templates: list[str] = Field(default_factory=list)


@lru_cache(maxsize=64)
def load_brand_kit(brand_kit_id: str) -> BrandKit:
    path = _BRAND_KITS_DIR / f"{brand_kit_id}.json"
    if not path.exists():
        avail = ", ".join(brand_kit_ids())
        raise ValueError(f"unknown brand kit {brand_kit_id!r}; available: {avail}")
    return BrandKit.model_validate_json(path.read_text())


def list_brand_kits() -> list[BrandKit]:
    if not _BRAND_KITS_DIR.exists():
        return []
    return [
        BrandKit.model_validate_json(p.read_text())
        for p in sorted(_BRAND_KITS_DIR.glob("*.json"))
    ]


def brand_kit_ids() -> list[str]:
    if not _BRAND_KITS_DIR.exists():
        return []
    return sorted(p.stem for p in _BRAND_KITS_DIR.glob("*.json"))


__all__ = ["BrandKit", "load_brand_kit", "list_brand_kits", "brand_kit_ids"]
