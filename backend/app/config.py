from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings:
    """Process-wide configuration. Override via env vars."""

    def __init__(self) -> None:
        self.repo_root: Path = REPO_ROOT
        self.out_dir: Path = Path(os.environ.get("OUT_DIR", str(REPO_ROOT / "out"))).resolve()
        self.assets_dir: Path = Path(os.environ.get("ASSETS_DIR", str(REPO_ROOT / "assets"))).resolve()
        self.brand_kits_dir: Path = (REPO_ROOT / "brand_kits").resolve()
        self.scenarios_dir: Path = (REPO_ROOT / "out" / "scenarios").resolve()
        self.jobs_dir: Path = Path(os.environ.get("JOBS_DIR", str(REPO_ROOT / "out" / "jobs"))).resolve()
        self.max_cost_usd_per_job: float = float(os.environ.get("MAX_COST_USD_PER_JOB", "2.00"))
        self.allow_origins: list[str] = os.environ.get(
            "CORS_ALLOW_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        self.product_name: str = os.environ.get("PRODUCT_NAME", "CanvasKit")
        self.product_tagline: str = os.environ.get(
            "PRODUCT_TAGLINE",
            "Brief to brand-ready creative in under a minute.",
        )

    def ensure_dirs(self) -> None:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
