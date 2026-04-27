from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

_TEMPLATES_DIR = Path(__file__).parent


class Region(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)


class Scrim(BaseModel):
    shape: Literal["halo", "full-band", "rounded-block"] = "halo"
    color: str = "#000000"
    opacity: float = Field(ge=0.0, le=1.0, default=0.4)


class Typography(BaseModel):
    alignment: Literal["left", "center", "right"] = "left"
    font_size_pct: float = 6.0
    color_hint: str | None = None
    scrim: Scrim = Field(default_factory=Scrim)


class Template(BaseModel):
    id: str
    name: str
    brands: list[str] = Field(default_factory=list)
    description: str = ""
    regions: dict[str, Region] = Field(default_factory=dict)
    gen_directive: str = ""
    copy_zone: str | None = None
    typography: Typography = Field(default_factory=Typography)
    placement_hint: str = ""


@lru_cache(maxsize=64)
def load_template(template_id: str) -> Template:
    path = _TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        avail = ", ".join(template_ids())
        raise ValueError(f"unknown template {template_id!r}; available: {avail}")
    return Template.model_validate_json(path.read_text())


def list_templates() -> list[Template]:
    return [Template.model_validate_json(p.read_text()) for p in sorted(_TEMPLATES_DIR.glob("*.json"))]


def template_ids() -> list[str]:
    return sorted(p.stem for p in _TEMPLATES_DIR.glob("*.json"))


__all__ = ["Region", "Scrim", "Typography", "Template", "load_template", "list_templates", "template_ids"]
