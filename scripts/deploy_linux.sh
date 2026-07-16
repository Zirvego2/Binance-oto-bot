#!/usr/bin/env bash
# Ubuntu VPS uzerinde Docker + proje kurulumu (ilk kurulum).
# Kullanim: bash scripts/deploy_linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Bu script root olarak calistirilmalidir (sudo bash scripts/deploy_linux.sh)"
  exit 1
fi

echo "==> Sistem paketleri..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git unzip ufw

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Docker kuruluyor..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "HATA: docker compose bulunamadi. Docker kurulumunu kontrol edin."
  exit 1
fi

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "==> .env.example -> .env kopyalandi. Duzenleyip tekrar calistirin."
    exit 0
  fi
  echo "HATA: .env dosyasi yok. WinSCP ile yukleyin veya cp .env.example .env"
  exit 1
fi

if ! grep -q '^POSTGRES_PASSWORD=' .env || grep -q 'trading_bot$' .env 2>/dev/null; then
  echo "UYARI: .env icinde guclu POSTGRES_PASSWORD kullanin."
fi

if [[ ! -f /swapfile ]] && [[ "$(free -m | awk '/^Mem:/{print $2}')" -lt 8192 ]]; then
  echo "==> 2 GB swap ekleniyor (4 GB RAM icin onerilir)..."
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Firewall..."
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 80/tcp >/dev/null 2>&1 || true
ufw allow 443/tcp >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

echo "==> Docker Compose build + start..."
docker compose up -d --build

echo "==> Servis durumu:"
docker compose ps

echo ""
echo "Kurulum tamam. Admin olusturmak icin:"
echo "  docker compose exec api python scripts/create_admin.py"
echo ""
echo "Panel: http://$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
