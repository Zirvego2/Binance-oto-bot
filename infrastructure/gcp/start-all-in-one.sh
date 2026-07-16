#!/bin/sh
set -eu

PORT="${PORT:-8080}"
export PORT

echo "[start] Black Crypto AI Bot - all-in-one (port=${PORT})"

envsubst '${PORT}' < /etc/nginx/nginx.template.conf > /tmp/nginx.conf

echo "[start] Alembic migration..."
cd /app/services/api
alembic upgrade head || echo "[warn] migration failed, devam ediliyor..."

echo "[start] Bootstrap admin hesaplari..."
python scripts/bootstrap_cloud_admin.py || echo "[warn] bootstrap admin atlandi"

echo "[start] API..."
uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers &
API_PID=$!

echo "[start] Worker..."
cd /app/services/worker
SKIP_PROCESS_LOCK=true ALL_IN_ONE=true python -m worker.main &
WORKER_PID=$!

echo "[start] Web..."
cd /app/web
PORT=3000 HOSTNAME=127.0.0.1 node server.js &
WEB_PID=$!

sleep 5

if ! kill -0 "$API_PID" 2>/dev/null; then
  echo "[error] API baslamadi"
  exit 1
fi

echo "[start] Nginx..."
exec nginx -c /tmp/nginx.conf -g 'daemon off;'
