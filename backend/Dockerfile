# syntax=docker/dockerfile:1

# ---- build: resolve and install runtime dependencies into /app/.venv ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# uv.lock is optional until it is committed; the wildcard keeps the COPY valid either way.
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

COPY agilesim ./agilesim

# ---- runtime: no uv, no build tools, non-root user ----
FROM python:3.13-slim-bookworm AS runtime
RUN useradd --system --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
# Apply pending migrations (as the schema owner), then start the API (as the limited role).
CMD ["sh", "-c", "python -m agilesim.db.migrate && exec uvicorn agilesim.main:app --host 0.0.0.0 --port 8000"]
