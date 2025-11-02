# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl nodejs npm \
    && npm install -g cline \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

ENV CLINE_DISABLE_AUTO_UPDATE=1 \
    CLINE_CLI_DISABLE_AUTO_UPDATE=1 \
    POSTHOG_TELEMETRY_ENABLED=false

COPY . .

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
