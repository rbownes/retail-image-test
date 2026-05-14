"""Read-only scanner over `out/scenarios/` for the gallery API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.config import get_settings

# Subdirs under out/scenarios that are NOT real scenarios.
_RESERVED = {"old", "share", "_archive"}


def _scenario_dirs() -> list[Path]:
    scen_root = get_settings().scenarios_dir
    if not scen_root.exists():
        return []
    return sorted(
        p
        for p in scen_root.iterdir()
        if p.is_dir() and p.name not in _RESERVED and not p.name.startswith(".")
    )


def list_gallery() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    settings = get_settings()
    summary_costs = _load_summary_costs()
    for d in _scenario_dirs():
        final = d / "final.png"
        raw = d / "raw.png"
        spec_path = d / "spec.json"
        if not final.exists():
            continue
        spec = None
        if spec_path.exists():
            try:
                spec = json.loads(spec_path.read_text())
            except json.JSONDecodeError:
                spec = None
        rel_final = final.relative_to(settings.repo_root).as_posix()
        rel_raw = raw.relative_to(settings.repo_root).as_posix() if raw.exists() else None
        items.append(
            {
                "id": d.name,
                "theme": _humanize(d.name),
                "final_url": f"/static/{rel_final}",
                "raw_url": f"/static/{rel_raw}" if rel_raw else None,
                "spec": spec,
                "cost_usd": summary_costs.get(d.name),
            }
        )
    return items


def get_gallery_item(scenario_id: str) -> dict[str, Any] | None:
    for item in list_gallery():
        if item["id"] == scenario_id:
            return item
    return None


def _humanize(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def _load_summary_costs() -> dict[str, float]:
    summary = get_settings().scenarios_dir / "summary.json"
    if not summary.exists():
        return {}
    try:
        data = json.loads(summary.read_text())
    except json.JSONDecodeError:
        return {}
    out: dict[str, float] = {}
    # Best-effort: each result row may have an `id` and inferable cost via per-result data.
    # The existing summary.json carries a top-level usage_log; per-scenario cost isn't broken out,
    # so we approximate evenly when present.
    total = data.get("total_cost_usd")
    results = data.get("results") or []
    if total and results:
        share = total / len(results)
        for r in results:
            if "id" in r:
                out[r["id"]] = round(share, 4)
    return out
