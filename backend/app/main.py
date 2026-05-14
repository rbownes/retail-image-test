from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import get_settings
from backend.app.routes import brand_kits, gallery, jobs, templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.product_name,
        description=settings.product_tagline,
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static mounts — served at /static/<repo-relative-path>
    app.mount("/static/out", StaticFiles(directory=str(settings.out_dir)), name="out")
    app.mount("/static/assets", StaticFiles(directory=str(settings.assets_dir)), name="assets")

    # Job artifacts (raw.png / final.png / spec.json per job) under /static/jobs
    # are inside out/jobs by default, so they are already served by the /static/out mount
    # via the path "/static/out/jobs/<id>/final.png". We also expose them at the cleaner
    # "/static/jobs/<id>/..." prefix for nicer URLs.
    app.mount("/static/jobs", StaticFiles(directory=str(settings.jobs_dir)), name="jobs")

    app.include_router(brand_kits.router)
    app.include_router(templates.router)
    app.include_router(gallery.router)
    app.include_router(jobs.router)

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "product": settings.product_name,
            "tagline": settings.product_tagline,
            "version": "0.2.0",
        }

    return app


app = create_app()
