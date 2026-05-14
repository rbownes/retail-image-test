"""Cost estimation for the UI's pre-run preview.

Uses out/scenarios/summary.json as the median basis, plus the published OpenAI
flat-rate image pricing and Claude per-token rates (a critique pass is roughly
2.7K in / 150 out on Opus 4.7).
"""

from __future__ import annotations

import json
from typing import Any

from backend.app.config import get_settings

# Per-call medians sourced from out/scenarios/summary.json (Opus 4.7 placement +
# critique, gpt-image-1 medium 1024²). Refine with real data when available.
_CRITIQUE_MEDIAN_USD = 0.018
_PLACEMENT_MEDIAN_USD = 0.018
_OPENAI_IMAGE_FLAT = {
    "low": 0.011,
    "medium": 0.042,
    "high": 0.167,
    "auto": 0.042,
}


def estimate_cost(req: dict[str, Any]) -> dict[str, float]:
    provider = req.get("provider", "openai")
    quality = req.get("quality", "medium")
    max_iter = int(req.get("max_iterations", 3))

    if provider == "openai":
        per_image = _OPENAI_IMAGE_FLAT.get(quality, _OPENAI_IMAGE_FLAT["medium"])
    else:
        per_image = 0.0  # local SD

    # Best case: 1 iteration, no critique, then placement.
    best = per_image + _PLACEMENT_MEDIAN_USD
    # Expected: typical median (1.3 iterations) + 1 critique + 1 placement.
    expected = per_image * 1.3 + _CRITIQUE_MEDIAN_USD * max(0, max_iter - 1) * 0.3 + _PLACEMENT_MEDIAN_USD
    # Worst case: all iterations + critique each + placement.
    worst = per_image * max_iter + _CRITIQUE_MEDIAN_USD * max(0, max_iter - 1) + _PLACEMENT_MEDIAN_USD

    return {
        "min": round(best, 4),
        "expected": round(expected, 4),
        "max": round(worst, 4),
        "per_image": round(per_image, 4),
    }


def real_median_per_image() -> float | None:
    """Try to read a real per-image median from out/scenarios/summary.json."""
    p = get_settings().scenarios_dir / "summary.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return None
    total = data.get("total_cost_usd")
    results = data.get("results") or []
    if total and results:
        return round(total / len(results), 4)
    return None
