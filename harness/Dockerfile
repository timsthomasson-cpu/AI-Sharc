# AI Sharc harness on Railway. Build context: the repo root (Railway dockerfilePath = harness/Dockerfile).
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app

COPY harness/requirements.txt /app/harness/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 && rm -rf /var/lib/apt/lists/* \
 && pip install -r /app/harness/requirements.txt \
 && python -m playwright install --with-deps chromium

COPY harness /app/harness
COPY orchestrator /app/orchestrator
COPY loader /app/loader

# Self-check by default; set RUN_QUERY_ID to audit one query (see orchestrator/railway_start.py).
CMD ["python", "/app/orchestrator/railway_start.py"]
