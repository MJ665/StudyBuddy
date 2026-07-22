# StudyBuddy API — long-running container (Railway/Render/Fly/ECS).
# A persistent process is required: APScheduler cron + the durable job worker
# assume a long-lived runtime (they do NOT work on ephemeral serverless).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# System deps: build tools for any wheels that need compiling, libpq for psycopg2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code.
COPY . .

# Drop root.
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness/readiness are served by the app (/health, /ready).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

# Single web process. The APScheduler cron is guarded by RUN_SCHEDULER so that when
# you scale to multiple instances, only ONE runs the scheduler (avoids duplicate jobs).
# Set RUN_SCHEDULER=true on exactly one instance (or run a dedicated worker instance).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
