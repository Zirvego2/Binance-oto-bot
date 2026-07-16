# Ubuntu VPS Kurulum Rehberi (Docker Compose)

Bu rehber, projeyi **Ubuntu 20.04+** sunucuda (ör. XCloud VPS) production ortamında çalıştırmak içindir.

**Sunucu IP örneği:** `185.22.184.249`  
**Panel adresi:** `https://novexcrypto.com` (SSL kurulumundan sonra)

---

## 1. Sunucuya bağlanın (PuTTY)

- Host: sunucu IP adresi
- Port: `22`
- Kullanıcı: genelde `root` (hosting panelindeki bilgiye göre)

---

## 2. Sistem güncellemesi ve Docker kurulumu

PuTTY terminalinde sırayla:

```bash
apt update && apt upgrade -y
apt install -y ca-certificates curl git unzip ufw
```

Docker kurulum scripti:

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
```

Docker Compose eklentisini doğrulayın:

```bash
docker compose version
```

4 GB RAM için swap (önerilir):

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

Firewall:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

---

## 3. Projeyi sunucuya aktarın

### Seçenek A — Git ile (repo varsa)

```bash
cd /opt
git clone <REPO_URL> binance-oto-bot
cd binance-oto-bot
```

### Seçenek B — Windows'tan ZIP ile (WinSCP)

1. Bilgisayarınızda proje klasörünü ZIP'leyin (`node_modules`, `.git`, `__pycache__` hariç).
2. [WinSCP](https://winscp.net) ile `/opt/binance-oto-bot.zip` yükleyin.
3. Sunucuda:

```bash
mkdir -p /opt/binance-oto-bot
cd /opt
unzip -o binance-oto-bot.zip -d binance-oto-bot
cd binance-oto-bot
```

---

## 4. `.env` dosyasını hazırlayın

Yerel bilgisayarınızdaki `.env` dosyasını WinSCP ile sunucuya kopyalayın:

```
/opt/binance-oto-bot/.env
```

**Production için mutlaka güncelleyin** (IP veya domain'inize göre):

```env
APP_ENV=production
WEB_ORIGIN=http://185.22.184.249
API_ORIGIN=http://185.22.184.249
APP_TIMEZONE=Europe/Istanbul
SECURE_COOKIES=false

POSTGRES_PASSWORD=guclu-bir-sifre-buraya

NEXT_PUBLIC_API_BASE_URL=/api/v1
NEXT_PUBLIC_WS_BASE_URL=/api/v1
```

Firebase kullanıyorsanız `firebase-service-account.json` dosyasını da proje köküne yükleyin.

`.env` içindeki `DATABASE_URL` ve `REDIS_URL` satırları Docker Compose tarafından container içinde otomatik ezilir; yerel SQLite URL'i kalabilir.

---

## 5. Botu başlatın

```bash
cd /opt/binance-oto-bot
docker compose up -d --build
```

İlk build 10–20 dakika sürebilir. Durumu kontrol:

```bash
docker compose ps
docker compose logs -f --tail=50
```

Tüm servisler `running` / `healthy` olmalı.

---

## 6. Admin kullanıcısı

```bash
docker compose exec api python scripts/create_admin.py
```

`.env` içindeki `ADMIN_EMAIL` ve `ADMIN_PASSWORD` ile giriş yapın.

---

## 7. Binance API IP whitelist

Sunucu IP'sini (`185.22.184.249`) **tüm müşteri Binance API anahtarlarında** whitelist'e ekleyin. Bot bu IP üzerinden Binance'e bağlanır.

---

## 8. Panel erişimi

Tarayıcıda: **http://185.22.184.249**

- Admin paneli giriş
- Bot Kontrol → mod seçimi (önce PAPER ile test)
- LIVE için paneldeki güvenlik onay adımlarını tamamlayın

---

## Yararlı komutlar

```bash
# Loglar
docker compose logs -f api
docker compose logs -f worker

# Yeniden başlat
docker compose restart

# Güncelleme (yeni kod yükledikten sonra)
docker compose up -d --build

# Durdur
docker compose down

# Veritabanı dahil tamamen sil (dikkat!)
docker compose down -v
```

---

## Sorun giderme

| Sorun | Çözüm |
|--------|--------|
| Panel açılmıyor | `docker compose ps`, `ufw status`, port 80 açık mı |
| API 502 | `docker compose logs api`, migrate tamamlandı mı |
| Binance bağlantı hatası | IP whitelist, API key izinleri (Futures, IP kısıtı) |
| Bellek yetersiz | Swap ekleyin, gereksiz servisleri kapatın |

---

## HTTPS ve domain (novexcrypto.com)

### 1. DNS ayarlari (domain panelinde)

| Tip | Ad (Host) | Deger | TTL |
|-----|-----------|-------|-----|
| A   | `@`       | `185.22.184.249` | 300 |
| A   | `www`     | `185.22.184.249` | 300 |

DNS yayilmasi 5–30 dakika surebilir. Kontrol:

```bash
dig +short novexcrypto.com
dig +short www.novexcrypto.com
```

Her ikisi de `185.22.184.249` donmeli.

### 2. Guncel dosyalari sunucuya yukleyin

WinSCP ile su dosyalari `/opt/binance-oto-bot/` altina kopyalayin:

- `docker-compose.yml`
- `infrastructure/nginx/nginx.conf`
- `infrastructure/nginx/nginx.init.conf`
- `infrastructure/nginx/nginx.ssl.conf`
- `scripts/setup_ssl.sh`
- `.env.production` → `.env` olarak (HTTPS degerleriyle)

### 3. SSL kurulum scriptini calistirin

PuTTY ile sunucuda:

```bash
cd /opt/binance-oto-bot
chmod +x scripts/setup_ssl.sh
./scripts/setup_ssl.sh
```

Script sirasiyla:

1. Let's Encrypt sertifikasi alir (`novexcrypto.com` + `www`)
2. Nginx'i HTTPS yapilandirmasina gecirir
3. HTTP ve IP erisimini `https://novexcrypto.com` adresine yonlendirir
4. `.env` icinde `WEB_ORIGIN`, `API_ORIGIN`, `SECURE_COOKIES=true` ayarlar
5. API'yi yeniden baslatir (Secure cookie)
6. Sertifika yenileme cron'u ekler

### 4. Admin kullanicisi (platform yonetici)

```bash
docker compose exec api python scripts/create_admin.py
docker compose restart api
```

Giris adresleri:

- **Musteri:** https://novexcrypto.com/login
- **Admin:** https://novexcrypto.com/admin/login

---

## HTTPS (manuel kurulum — alternatif)

Domain DNS A kaydini sunucu IP'sine yonlendirin, sonra:

```bash
apt install -y certbot
# Nginx container disinda cert almak icin gecici olarak port 80'i bosaltin veya
# hosting panelinden Let's Encrypt sertifikasi kullanin.
```

HTTPS sonrasi `.env` icinde:

```env
WEB_ORIGIN=https://novexcrypto.com
API_ORIGIN=https://novexcrypto.com
SECURE_COOKIES=true
```

Ardindan: `docker compose restart api nginx`
