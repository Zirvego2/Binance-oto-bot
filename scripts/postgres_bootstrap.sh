#!/usr/bin/env bash
# PostgreSQL ilk kurulum (Alembic migration sorunlarini atlar).
# Kullanim: bash scripts/postgres_bootstrap.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Eski container/volume temizligi..."
docker compose down -v

echo "==> Postgres + Redis baslatiliyor..."
docker compose up -d postgres redis

echo "==> Postgres hazir olana kadar bekleniyor..."
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-trading_bot}" -d "${POSTGRES_DB:-trading_bot}" >/dev/null 2>&1; then
    echo "Postgres hazir."
    break
  fi
  sleep 2
  if [[ "$i" -eq 30 ]]; then
    echo "HATA: Postgres hazir degil."
    exit 1
  fi
done

echo "==> API image build..."
docker compose build api migrate

echo "==> Tablolar SQLAlchemy ile olusturuluyor..."
docker compose run --rm --no-deps api python -c "
import asyncio
from app.core.database import create_all_tables
asyncio.run(create_all_tables())
print('Tablolar olusturuldu.')
"

echo "==> Alembic surumu isaretleniyor (head)..."
docker compose run --rm migrate alembic stamp head

echo "==> Tum servisler baslatiliyor..."
docker compose up -d

echo "==> Durum:"
docker compose ps

echo ""
echo "Admin olusturmak icin:"
echo "  docker compose exec api python scripts/create_admin.py"
