#!/usr/bin/env bash
# Yerel SQLite (trading_bot.db) -> sunucu PostgreSQL aktarimi
#
# 1) WinSCP ile trading_bot.db dosyasini sunucuya yukleyin:
#      /opt/binance-oto-bot/trading_bot.db
# 2) WinSCP ile script dosyalarini yukleyin:
#      services/api/scripts/migrate_sqlite_to_postgres.py
#      scripts/import_local_data.sh
# 3) Calistirin:
#      sed -i 's/\r$//' scripts/import_local_data.sh
#      chmod +x scripts/import_local_data.sh
#      ./scripts/import_local_data.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SQLITE_FILE="${PROJECT_DIR}/trading_bot.db"
MIGRATE_SCRIPT="${PROJECT_DIR}/services/api/scripts/migrate_sqlite_to_postgres.py"

cd "${PROJECT_DIR}"

if [[ ! -f "${SQLITE_FILE}" ]]; then
  echo "HATA: ${SQLITE_FILE} bulunamadi."
  echo "WinSCP ile yerel trading_bot.db dosyasini bu konuma yukleyin."
  exit 1
fi

if [[ ! -f "${MIGRATE_SCRIPT}" ]]; then
  echo "HATA: ${MIGRATE_SCRIPT} bulunamadi."
  exit 1
fi

echo "==> Servisler durduruluyor (api, worker)..."
docker compose stop api worker

echo "==> Veri aktarimi basliyor (~78MB, birkaÃ§ dakika surebilir)..."
docker compose run --rm --no-deps \
  -v "${SQLITE_FILE}:/tmp/trading_bot.db:ro" \
  -v "${MIGRATE_SCRIPT}:/app/services/api/scripts/migrate_sqlite_to_postgres.py:ro" \
  api python scripts/migrate_sqlite_to_postgres.py /tmp/trading_bot.db

echo "==> Servisler baslatiliyor..."
docker compose start api worker

echo ""
echo "Tamamlandi."
echo "Kontrol:"
echo "  docker compose exec postgres psql -U trading_bot -d trading_bot -c \"SELECT COUNT(*) FROM positions WHERE status='OPEN';\""
echo "  docker compose exec postgres psql -U trading_bot -d trading_bot -c \"SELECT email, role FROM admins;\""
