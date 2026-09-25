# syntax=docker/dockerfile:1

# ==========================================================================
# Builder — resolves the uv-managed venv from uv.lock. No requirements.txt
# needed: `uv sync --frozen` installs exactly what's pinned in the lockfile.
# ==========================================================================
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Dependencies first, separately from app code, so this (slow) layer is
# cached across code-only changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ==========================================================================
# Runtime — slim, no uv/build toolchain in the final image.
# ==========================================================================
FROM python:3.13-slim-bookworm AS runtime

# libgl1 / libglib2.0-0: opencv-python (a transitive dependency of rapidocr,
# used for server-side OCR) fails to import without them on Debian slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

CMD ["gunicorn", "lpg.api.app:app", "--config", "gunicorn.conf.py"]
