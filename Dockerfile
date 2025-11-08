# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

# Install system dependencies and uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl nodejs npm \
    && npm install -g cline \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

# Copy uv from official distroless image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CLINE_DISABLE_AUTO_UPDATE=1 \
    CLINE_CLI_DISABLE_AUTO_UPDATE=1 \
    POSTHOG_TELEMETRY_ENABLED=false \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first (better layer caching)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# Copy application code
COPY . .

# Install project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
