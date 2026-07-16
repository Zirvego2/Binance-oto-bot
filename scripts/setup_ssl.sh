#!/usr/bin/env bash
# Novex Crypto â€” Let's Encrypt SSL kurulumu (Ubuntu VPS + Docker Compose)
#
# Kullanim (sunucuda):
#   cd /opt/binance-oto-bot
#   chmod +x scripts/setup_ssl.sh
#   ./scripts/setup_ssl.sh
#
# Onkosul: DNS A kaydi novexcrypto.com ve www -> sunucu IP (185.22.184.249)

set -euo pipefail

DOMAIN="novexcrypto.com"
WWW_DOMAIN="www.novexcrypto.com"
EMAIL="${SSL_EMAIL:-admin@${DOMAIN}}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTBOT_WEBROOT="/var/www/certbot"
NGINX_INIT="${PROJECT_DIR}/infrastructure/nginx/nginx.init.conf"
NGINX_SSL="${PROJECT_DIR}/infrastructure/nginx/nginx.ssl.conf"
NGINX_ACTIVE="${PROJECT_DIR}/infrastructure/nginx/nginx.conf"
ENV_FILE="${PROJECT_DIR}/.env"

cd "${PROJECT_DIR}"

echo "==> DNS kontrolu (${DOMAIN})..."
RESOLVED_IP="$(getent ahostsv4 "${DOMAIN}" | awk '{print $1; exit}' || true)"
if [[ -z "${RESOLVED_IP}" ]]; then
  echo "HATA: ${DOMAIN} DNS kaydi bulunamadi. Once domain panelinden A kaydini ekleyin."
  exit 1
fi
echo "    ${DOMAIN} -> ${RESOLVED_IP}"

echo "==> Certbot kurulumu..."
apt-get update -qq
apt-get install -y certbot

echo "==> Webroot dizini..."
mkdir -p "${CERTBOT_WEBROOT}"

echo "==> Gecici HTTP nginx yapilandirmasi..."
cp "${NGINX_INIT}" "${NGINX_ACTIVE}"

echo "==> Nginx baslatiliyor (port 80)..."
docker compose up -d nginx

echo "==> Let's Encrypt sertifikasi aliniyor..."
certbot certonly \
  --webroot \
  -w "${CERTBOT_WEBROOT}" \
  -d "${DOMAIN}" \
  -d "${WWW_DOMAIN}" \
  --email "${EMAIL}" \
  --agree-tos \
  --non-interactive \
  --keep-until-expiring

echo "==> HTTPS nginx yapilandirmasi aktif ediliyor..."
cp "${NGINX_SSL}" "${NGINX_ACTIVE}"

echo "==> Firewall (443)..."
if command -v ufw >/dev/null 2>&1; then
  ufw allow 443/tcp || true
fi

echo "==> Nginx container yeniden olusturuluyor (443 port mapping)..."
docker compose up -d --force-recreate nginx
docker compose exec -T nginx nginx -t

echo "==> .env HTTPS ayarlari guncelleniyor..."
if [[ -f "${ENV_FILE}" ]]; then
  sed -i "s|^WEB_ORIGIN=.*|WEB_ORIGIN=https://${DOMAIN}|" "${ENV_FILE}"
  sed -i "s|^API_ORIGIN=.*|API_ORIGIN=https://${DOMAIN}|" "${ENV_FILE}"
  sed -i "s|^SECURE_COOKIES=.*|SECURE_COOKIES=true|" "${ENV_FILE}"
else
  echo "UYARI: ${ENV_FILE} bulunamadi â€” WEB_ORIGIN/API_ORIGIN/SECURE_COOKIES elle guncelleyin."
fi

echo "==> API yeniden baslatiliyor (Secure cookie)..."
docker compose restart api

echo "==> Otomatik yenileme (cron)..."
RENEW_HOOK="cd ${PROJECT_DIR} && docker compose exec -T nginx nginx -s reload"
CRON_LINE="0 3 * * * certbot renew --quiet --webroot -w ${CERTBOT_WEBROOT} --deploy-hook '${RENEW_HOOK}'"
( crontab -l 2>/dev/null | grep -v "certbot renew" || true; echo "${CRON_LINE}" ) | crontab -

echo ""
echo "Tamamlandi."
echo "  Panel: https://${DOMAIN}"
echo "  Admin: https://${DOMAIN}/admin/login"
echo "  IP erisimi otomatik olarak HTTPS domaine yonlendirilir."
echo ""
echo "Admin rolu icin (bir kez):"
echo "  docker compose exec api python scripts/create_admin.py"
