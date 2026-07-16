# Binance USDS-M Futures Otomatik Islem Botu - Worker servisi
# Bu Dockerfile REPO KOKUNDEN build edilmelidir:
#   docker build -f services/worker/Dockerfile -t trading-bot-worker .
# Cloud Run: GET /health uzerinden probe (PORT varsayilan 8080)

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    SKIP_PROCESS_LOCK=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/shared /app/packages/shared
COPY services/worker/requirements.txt /app/services/worker/requirements.txt

RUN pip install --upgrade pip \
    && pip install -e /app/packages/shared \
    && grep -v '^-e' /app/services/worker/requirements.txt | pip install -r /dev/stdin

COPY services/worker /app/services/worker

WORKDIR /app/services/worker

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f "http://127.0.0.1:${PORT}/health" || exit 1

CMD ["python", "-m", "worker.main"]
