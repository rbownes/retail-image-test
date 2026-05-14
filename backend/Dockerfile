# Slim backend image — OpenAI provider only. ~250 MB final.
# For local Stable Diffusion in docker, install the [local] extras instead
# (adds ~3 GB of torch + diffusers + transformers).

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pillow build deps (Debian-slim doesn't ship them).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo zlib1g libpng16-16 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps in a separate layer so source changes don't bust the cache.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
        "anthropic>=0.92.0" "openai>=1.50" "pydantic>=2.0" "Pillow>=10.0" \
        "fastapi>=0.110" "uvicorn[standard]>=0.27" "python-multipart>=0.0.9"

# Application code + bundled data (templates, brand kits, gallery, assets).
COPY overlay ./overlay
COPY backend ./backend
COPY brand_kits ./brand_kits
COPY assets ./assets
COPY out ./out

# Non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
