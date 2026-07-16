#!/usr/bin/env bash
# HTTPS (443) baglanti sorunu duzeltme â€” port mapping + firewall + nginx yeniden olusturma
#
# Kullanim:
#   cd /opt/binance-oto-bot
#   sed -i 's/\r$//' scripts/fix_https.sh
#   chmod +x scripts/fix_https.sh
#   ./scripts/fix_https.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NGINX_SSL="${PROJECT_DIR}/infrastructure/nginx/nginx.ssl.conf"
NGINX_ACTIVE="${PROJECT_DIR}/infrastructure/nginx/nginx.conf"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"

cd "${PROJECT_DIR}"

echo "==> docker-compose.yml 443 portu kontrolu..."
if ! grep -q '"443:443"' "${COMPOSE_FILE}"; then
  echo "HATA: docker-compose.yml icinde '443:443' yok."
  echo "Guncel docker-compose.yml dosyasini WinSCP ile yukleyin, sonra tekrar calistirin."
  exit 1
fi

echo "==> Firewall (443)..."
if command -v ufw >/dev/null 2>&1; then
  ufw allow 443/tcp || true
  ufw status | grep -E '443|Status' || true
fi

echo "==> Sertifika kontrolu..."
if [[ ! -f /etc/letsencrypt/live/novexcrypto.com/fullchain.pem ]]; then
  echo "HATA: SSL sertifikasi bulunamadi. Once ./scripts/setup_ssl.sh calistirin."
  exit 1
fi

echo "==> HTTPS nginx yapilandirmasi..."
cp "${NGINX_SSL}" "${NGINX_ACTIVE}"

echo "==> Nginx container yeniden olusturuluyor (443 port mapping icin)..."
docker compose up -d --force-recreate nginx

echo "==> Nginx yapilandirma testi..."
docker compose exec -T nginx nginx -t

echo "==> Port dinleme kontrolu..."
ss -tlnp | grep ':443' || echo "UYARI: 443 dinlenmiyor olabilir"

echo "==> Yerel HTTPS testi..."
curl -skI https://127.0.0.1/ | head -5 || echo "UYARI: localhost HTTPS testi basarisiz"

echo ""
echo "Tamamlandi. Tarayicida deneyin: https://novexcrypto.com/login"
echo "Hala acilmazsa XCloud/hosting panelinden 443 portunun acik oldugunu kontrol edin."
