# Binance USDⓈ-M Futures Otomatik İşlem Botu

Profesyonel, web tabanlı, **Binance USDⓈ-M Perpetual Futures** (Binance Spot DEĞİL) için geliştirilmiş otomatik işlem botu. PAPER (sanal), DEMO (Binance testnet) ve LIVE (gerçek para) modlarını destekler; teknik analiz tabanlı sinyal üretimi, sunucu taraflı (borsa üzerinde) stop-loss/take-profit koruması, kapsamlı risk yönetimi ve Türkçe bir admin paneli içerir.

> ⚠️ **UYARI / SORUMLULUK REDDİ**
> Bu yazılım **kâr garantisi vermez**. Kripto para vadeli işlemleri (özellikle kaldıraçlı) **yüksek risk** içerir ve **sermayenizin tamamını kaybetmenize** yol açabilir. Bu proje "olduğu gibi" (as-is) sunulmaktadır; herhangi bir finansal tavsiye niteliği taşımaz. LIVE moda geçmeden önce PAPER modda **uzun süre** test yapmanız şiddetle önerilir. Gerçek parayla kullanım tamamen kendi sorumluluğunuzdadır.

---

## İçindekiler

1. [Genel Bakış](#genel-bakış)
2. [Mimari](#mimari)
3. [Teknoloji Yığını](#teknoloji-yığını)
4. [Çalışma Modları (PAPER / DEMO / LIVE)](#çalışma-modları-paper--demo--live)
5. [Hızlı Başlangıç (Docker Compose)](#hızlı-başlangıç-docker-compose)
6. [Docker Olmadan Yerel Geliştirme](#docker-olmadan-yerel-geliştirme)
7. [Ortam Değişkenleri](#ortam-değişkenleri)
8. [Admin Paneli Kullanımı](#admin-paneli-kullanımı)
9. [Strateji ve Sinyal Mantığı](#strateji-ve-sinyal-mantığı)
10. [Risk Yönetimi](#risk-yönetimi)
11. [LIVE Moda Güvenli Geçiş](#live-moda-güvenli-geçiş)
12. [Proje Yapısı](#proje-yapısı)
13. [Testler](#testler)
14. [Güvenlik Notları](#güvenlik-notları)
15. [Sorun Giderme](#sorun-giderme)

---

## Genel Bakış

Bot, seçilen USDT-margined perpetual sözleşmeler üzerinde piyasayı periyodik olarak tarar, teknik göstergelere (EMA, RSI, ATR, hacim, spread, funding rate, açık pozisyon vb.) dayalı bir puanlama sistemiyle LONG/SHORT sinyalleri üretir, risk kontrollerinden geçen sinyaller için **ISOLATED marj** ve admin tarafından tanımlı kaldıraçla pozisyon açar ve pozisyon açılır açılmaz **borsa üzerinde** (server-side) STOP_MARKET / TAKE_PROFIT_MARKET algo emirleri yerleştirir. Bir pozisyon asla koruyucu emirsiz açık bırakılmaz: SL veya TP emri yerleşemezse pozisyon **anında** reduce-only market emriyle kapatılır.

Tüm işlemler, emirler, sinyaller, risk olayları ve sistem durumu, gerçek zamanlı (WebSocket) güncellenen Türkçe bir admin panelinden izlenebilir.

## Mimari

Monorepo yapısı:

```
apps/web            -> Next.js (App Router) admin paneli
services/api         -> FastAPI backend (REST + WebSocket, kimlik doğrulama, ayarlar)
services/worker      -> Piyasa taraması, sinyal üretimi, emir yönetimi, pozisyon izleme
packages/shared      -> Ortak Decimal/finansal hesaplama, Binance adapter, DB modelleri
infrastructure/nginx -> Tek origin üzerinden web+API sunan reverse proxy
tests/               -> unit / integration / worker test paketleri
```

`api` ve `worker` birbirinden **bağımsız süreçlerdir** ve aynı PostgreSQL veritabanı üzerinden koordine olur (kritik bölümlerde Redis tabanlı dağıtık kilit kullanılır). `api` kullanıcı arayüzüne veri sağlar ve ayarları yönetir; `worker` piyasayı tarayan, sinyal üreten ve emir gönderen taraftır.

Binance'e hiçbir yerden doğrudan bağlanılmaz: her modül `BinanceFuturesAdapter` arayüzü üzerinden çalışır. `PaperFuturesAdapter` gerçek piyasa verisiyle (mark price, kline, funding rate) bellek içinde sanal hesap/pozisyon/emir simülasyonu yapar; `LiveFuturesAdapter` ise gerçek Binance USDⓈ-M Futures REST API'sine (DEMO modda testnet, LIVE modda gerçek) bağlanır.

## Teknoloji Yığını

- **Web paneli:** Next.js 14 (App Router), TypeScript, Tailwind CSS, Radix UI tabanlı bileşenler, TanStack Query, React Hook Form + Zod, Recharts, native WebSocket.
- **Backend API:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic, httpx, Redis, oturum tabanlı kimlik doğrulama + CSRF.
- **Worker:** Python 3.12, asyncio, Binance REST/WebSocket istemcisi, Redis dağıtık kilit.
- **Veritabanı / Altyapı:** PostgreSQL 16, Redis 7, Docker, Docker Compose, Nginx.
- **Finansal hesaplamalar:** Tüm para/miktar/fiyat/ROI hesaplamaları Python `decimal.Decimal` ile yapılır; float kesinlik hatalarından kaçınılır.

## Çalışma Modları (PAPER / DEMO / LIVE)

| Mod | API anahtarı gerekir mi? | Borsa | Açıklama |
|---|---|---|---|
| **PAPER** | Hayır | — (gerçek piyasa verisi, sanal hesap) | Gerçek Binance piyasa verileriyle (mark price, kline, funding) tamamen bellek içinde/DB'de simüle edilen sanal bakiye, pozisyon ve emirler. Varsayılan ve güvenli başlangıç modudur. |
| **DEMO** | Evet (Binance Futures **testnet** anahtarı) | `testnet.binancefuture.com` | Gerçek Binance testnet ortamında, sahte parayla gerçek API akışını test eder. |
| **LIVE** | Evet (gerçek Binance hesabı) | `fapi.binance.com` | **GERÇEK PARA** ile işlem yapar. Yalnızca admin panelindeki çok aşamalı güvenlik onayından sonra etkinleşir (bkz. [LIVE Moda Güvenli Geçiş](#live-moda-güvenli-geçiş)). |

Mod değişimi admin panelindeki **Bot Kontrol** sayfasından yapılır; worker süreci başlarken veritabanındaki modu okur ve o modda çalışır. Mod veritabanında değişse bile worker **yeniden başlatılana kadar** eski modda kalır ve bu durumu loglar (yanlışlıkla mod karışmasını önlemek için).

## Hızlı Başlangıç (Docker Compose)

Gereksinim: Docker ve Docker Compose kurulu olmalı.

```bash
git clone <bu-repo>
cd Binance-Oto-Bot
cp .env.example .env
# .env icindeki APP_SECRET, APP_ENCRYPTION_KEY, ADMIN_EMAIL, ADMIN_PASSWORD
# degerlerini kendi ortaminiza gore duzenleyin.

docker compose up -d --build
```

Servisler ayağa kalktıktan sonra (`migrate` servisi Alembic migration'larını otomatik uygular):

```bash
# Ilk admin kullanicisini olustur (API container'i icinde)
docker compose exec api python scripts/create_admin.py
```

Panel: **http://localhost** (Nginx tüm trafiği tek origin üzerinden yönlendirir; API `/api/v1/*` altında sunulur).

Servisleri durdurmak için: `docker compose down` (verileri de silmek isterseniz `docker compose down -v`).

## Google Cloud Run (Production)

**Hesap:** `zirvego100@gmail.com`

Cloud Run deploy rehberi ve scriptler:

```powershell
# Ilk kurulum (GCP proje ID ile)
.\infrastructure\gcp\setup.ps1 -ProjectId "SIZIN-PROJE-ID"

# Ortam dosyasi
Copy-Item infrastructure\gcp\env.gcp.example infrastructure\gcp\env.gcp
# env.gcp duzenleyin, sonra:
.\infrastructure\gcp\deploy.ps1
```

Detayli adimlar: [`infrastructure/gcp/DEPLOY.md`](infrastructure/gcp/DEPLOY.md)

## Docker Olmadan Yerel Geliştirme

### 1. Backend (API + Worker)

```bash
cd Binance-Oto-Bot
cp .env.example .env   # DATABASE_URL varsayilan olarak SQLite kullanir, ek kurulum gerektirmez

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -e packages/shared
pip install -r services/api/requirements.txt
pip install -r services/worker/requirements.txt

# Ilk admin kullanicisini olustur
cd services/api
python scripts/create_admin.py
cd ../..

# API'yi baslat (1. terminal)
cd services/api
uvicorn app.main:app --reload --port 8000

# Worker'i baslat (2. terminal, ayni .env'i kullanir)
cd services/worker
python -m worker.main
```

### 2. Web Paneli

```bash
cd apps/web
cp .env.local.example .env.local
# NEXT_PUBLIC_API_BASE_URL ve NEXT_PUBLIC_WS_BASE_URL degerlerini
# http://localhost:8000/api/v1 ve ws://localhost:8000/api/v1 olarak ayarlayin
# (Nginx KULLANMADIGINIZ icin goreli yol calismaz).

npm install
npm run dev
```

Panel: **http://localhost:3000**

## Ortam Değişkenleri

Tüm değişkenler `.env.example` dosyasında açıklamalarıyla listelenmiştir. En önemlileri:

| Değişken | Açıklama |
|---|---|
| `APP_SECRET`, `APP_ENCRYPTION_KEY` | Oturum imzalama ve LIVE API secret şifreleme için kullanılır. **Production'da mutlaka değiştirin.** |
| `DATABASE_URL` / `REDIS_URL` | Docker Compose kullanılırken otomatik ezilir; yerel geliştirmede kullanılır. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `create_admin.py` scripti tarafından okunur (yalnızca ilk kurulumda). |
| `BINANCE_ENV` | `paper` \| `demo` \| `live` — worker'ın başlangıç modu (DB'deki `bot_settings.mode` ile tutarlı olmalı). |
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | DEMO/LIVE modları için Binance Futures API anahtarları. PAPER modda gerekmez. |
| `ENABLE_LIVE_TRADING` | `false` olduğu sürece LIVE moda geçiş **backend tarafında tamamen engellenir**; bilerek `true` yapmadan LIVE mod aktifleşmez. |
| `MAX_ALLOWED_LEVERAGE` | Sistem genelinde izin verilen mutlak maksimum kaldıraç tavanı. |
| `PAPER_START_BALANCE_USDT` | PAPER moddaki sanal baslangic bakiyesi. |
| `OPENAI_API_KEY` | GPT sinyal filtresi icin (opsiyonel, worker okur). |

> **Not:** `BINANCE_API_KEY`/`SECRET` gibi gerçek sırlar sadece `.env` dosyasında tutulur (bu dosya `.gitignore` ile repoya asla eklenmez) ve veritabanına yazılmaz.

## Admin Paneli Kullanımı

Giriş yaptıktan sonra sol menüden şu sayfalara erişilir:

- **Dashboard:** Anlık bakiye, toplam/günlük PnL, açık pozisyon sayısı, günlük istatistik grafiği, gerçek zamanlı açık pozisyonlar (WebSocket).
- **Pozisyonlar:** Açık/kapalı pozisyonlar, manuel kapatma.
- **Emirler:** Tüm market ve algo (SL/TP) emirleri.
- **İşlemler:** Kapanmış işlemler (trade) geçmişi ve PnL özeti.
- **Sinyaller & Analiz:** Üretilen sinyaller ve arkasındaki teknik analiz detayları (puan kırılımı dahil).
- **Semboller:** Taranan tüm coinler, piyasa verileri; sembol bazlı LONG/SHORT aç-kapa ve kara listeye alma.
- **Binance Bağlantısı:** Bağlantı testi, hesap özeti, açık pozisyon/algo emir listesi, manuel reconciliation (mutabakat) tetikleme.
- **Loglar:** Bot olayları, risk olayları, denetim (audit) kayıtları.
- **Ayarlar:** Kaldıraç, marj tipi, TP/SL ROI yüzdeleri, risk limitleri, gösterge periyotları, sinyal eşikleri vb. **tüm** bot parametreleri.
- **Bot Kontrol:** Botu baslat/durdur, acil durdur (emergency stop), mod degistir (PAPER/DEMO/LIVE — LIVE icin cok asamali onay akisi).

Worker her tarama döngüsünde (varsayılan 60 sn) şu adımları izler:

1. **Sembol seçimi:** 24 saatlik USDT hacmine göre en yüksek hacimli N sembol (varsayılan 20) adaylar arasına alınır; kara listedekiler ve `in_analysis_list=false` olanlar hariç tutulur.
2. **Gösterge hesaplama:** Her aday için EMA(9/21/50), RSI(14), ATR(14), hacim çarpanı, spread %, funding rate, açık pozisyon değişimi hesaplanır.
3. **Sinyal değerlendirme:** LONG için EMA hızlının orta/yavaş üzerinde olması + RSI aralığı (50-65) + hacim teyidi; SHORT için tam tersi koşullar aranır. Aşırı spread, aşırı funding rate veya aşırı volatilite (ATR%) varsa sinyal **hard-block** edilir.
4. **Puanlama:** Koşulları sağlayan sinyaller 0-100 arası bir skorla puanlanır (`min_signal_score` altındakiler elenir); puan kırılımı DB'de saklanır ve panelde gösterilir.
5. **Risk kontrolü:** `evaluate_portfolio_risk` — bot etkin mi, günlük zarar limiti, üst üste kayıp sayısı, maksimum açık pozisyon (genel/sembol bazlı), cooldown, kaldıraç tavanı gibi hesap seviyesi kontrolleri yapar.
6. **Pozisyon açma:** Tüm kontrollerden geçen sinyal için kaldıraç/marj tipi ayarlanır, Binance filtrelerine (`LOT_SIZE`, `PRICE_FILTER`, `MIN_NOTIONAL`) uygun miktar hesaplanır, market emri gönderilir, ardından ROI tabanlı SL/TP fiyatları hesaplanıp borsada algo emirleri yerleştirilir.

## Risk Yönetimi

- **ROI tabanlı TP/SL:** Kaldıraç dikkate alınarak fiyat hedefleri, admin'in tanımladığı **yatırılan marja göre ROI %** hedeflerinden geriye hesaplanır (basit fiyat yüzdesi değildir).
- **Likidasyona mesafe kontrolü:** Stop-loss fiyatı, tahmini likidasyon fiyatına admin tanımlı minimum mesafeden (`min_liquidation_distance_pct`) daha yakınsa pozisyon açılmaz.
- **Korumasız pozisyon yasağı:** SL veya TP emri borsada yerleşemezse pozisyon **anında** kapatılır; kapatma da başarısız olursa sistem `SAFE_MODE`'a geçer ve admin'e bildirilir.
- **Günlük zarar limiti / üst üste kayıp limiti:** Aşıldığında yeni pozisyon açılmaz.
- **Cooldown:** Bir sembolde pozisyon kapandıktan sonra admin tanımlı süre boyunca o sembolde yeni pozisyon açılmaz.
- **Reconciliation (mutabakat):** Worker periyodik olarak yerel veritabanı durumunu borsadaki gerçek durumla karşılaştırır; uyumsuzluk tespit edilirse loglanır ve panelde gösterilir.

## LIVE Moda Güvenli Geçiş

LIVE modun **yanlışlıkla** etkinleşmesini önlemek için birden çok bağımsız güvenlik katmanı vardır:

1. `.env` içinde `ENABLE_LIVE_TRADING=true` olmalı (varsayılan `false` — backend bu bayrak kapalıyken LIVE'a geçişi kesin olarak reddeder).
2. Geçerli, LIVE izinli bir `BINANCE_API_KEY`/`SECRET` tanımlı olmalı ve bağlantı testi (futures hesabı erişimi, işlem izni) başarılı olmalı.
3. Admin panelindeki **Bot Kontrol** sayfasında mod değişimi, admin'in belirli bir onay metnini birebir yazmasını gerektiren çok aşamalı bir diyalog ile korunur.
4. Geçiş, denetim (audit) logunda kalıcı olarak kayıt altına alınır.

Bu adımlardan biri eksikse LIVE moda geçiş engellenir ve nedeni panelde/loglarda gösterilir.

## Gelişmiş Karar Motoru (Enhanced Engine)

Varsayılan durum: **PAPER + Shadow Mode açık**, LIVE kapalı. Mevcut sinyal motoru emir açmaya devam eder; gelişmiş motor paralel analiz yapar ve karşılaştırır.

Akış: Piyasa verisi → rejim tespiti → sinyal analizi → risk puanı → R/R → aday sıralama → korelasyon → mevcut risk kontrolleri → (shadow) karar kaydı.

Admin paneli: Piyasa Rejimi, Aday Karşılaştırma, Coin Profilleri, Öğrenme Merkezi, Shadow Mode, Strateji Versiyonları.

Migration: `cd services/api && alembic upgrade head`

LIVE aktivasyonu için minimum: 100 shadow kararı, 30 kapanmış PAPER işlem, bot kapalı, açık pozisyon yok, onay metni: `CANLI STRATEJİYİ DEĞİŞTİR`.

GPT yalnızca açıklama üretir; emir kararı vermez.

## Proje Yapısı

```
apps/web/
  app/(dashboard)/...        Panel sayfalari (dashboard, positions, orders, trades, signals, symbols, binance, logs, settings, bot-control)
  app/login/                 Giris sayfasi
  components/                Paylasilan UI bilesenleri ve layout
  lib/                       API client, utils, TanStack Query provider
  hooks/                     use-auth, use-dashboard-ws
  middleware.ts              Route korumasi

services/api/app/
  api/routes/                REST + WebSocket endpointleri
  core/                      config, database, security, middleware
  services/                  Is mantigi (dashboard, bot control, paper state, reconciliation orchestration)
  schemas/                   Pydantic response/istek modelleri

services/worker/worker/
  main.py                    Ana orkestrasyon dongusu
  strategy.py                Sembol secimi + gosterge + sinyal degerlendirme
  risk.py                    Hesap/portfoy seviyesi risk kurallari
  order_engine.py            Pozisyon acma, koruyucu emir yerlestirme, acil kapatma
  position_monitor.py        Acik pozisyon PnL guncelleme, TP/SL tetiklenme tespiti
  market_sync.py             Exchange info / piyasa verisi senkronizasyonu
  reconciliation_task.py      Periyodik mutabakat
  mark_price_stream.py        Binance mark price WebSocket istemcisi
  redis_lock.py               Dagitik kilit

packages/shared/shared/
  binance/                   Adapter arayuzu, PaperFuturesAdapter, LiveFuturesAdapter, tipler, filtreler
  db/                        SQLAlchemy modelleri (Base + tum tablolar)
  position_sizing.py, roi.py, decimal_utils.py, signal_scoring.py, reconciliation.py, indicators.py, ...
  enhanced/                  Rejim, risk, R/R, korelasyon, shadow, backtest motorlari
  ai_explanation.py          Guvenli GPT aciklama (emir karari yok)

infrastructure/nginx/nginx.conf   Reverse proxy yapilandirmasi
docker-compose.yml                 Tum servislerin orkestrasyonu
```

## Testler

```bash
# Bagimliliklar kuruluysa (bkz. "Docker Olmadan Yerel Gelistirme")
python -m pytest tests -v
```

Test paketleri:

- `tests/unit/` — Decimal yardimcilari, Binance filtreleri, pozisyon boyutlandirma, ROI/likidasyon hesaplamalari, gostergeler, sinyal puanlama, PaperFuturesAdapter, reconciliation mantigi.
- `tests/integration/` — FastAPI uygulamasina karsi gercek HTTP istekleriyle kimlik dogrulama akisi (SQLite + fakeredis, gercek ag istegi ATILMAZ).
- `tests/worker/` — Worker'in risk motoru (`risk.py`), pozisyon acma motoru (`order_engine.py` — basarili acilis, koruyucu emir basarisizliginda acil kapatma, boyutlandirma reddi) ve pozisyon izleme (`position_monitor.py` — SL/TP tetiklenme, PnL guncelleme, gunluk istatistik/cooldown guncellemesi) testleri. Bu testler **gercek `PaperFuturesAdapter`** kodunu calistirir; sadece aga cikan `get_mark_price` metodu kontrollu bir fiyatla mocklanir, boylece tum is mantigi gercekci sekilde (network gerektirmeden, deterministik olarak) dogrulanir.

## Güvenlik Notları

- Şifreler `bcrypt` ile hash'lenir; oturumlar HTTP-only, `SameSite` korumalı çerezlerle yönetilir.
- Tüm state-changing (POST/PUT/PATCH/DELETE) istekler CSRF token doğrulaması gerektirir.
- Giriş denemeleri hız sınırlıdır (rate limit) ve tekrarlanan başarısız denemeler hesabı kilitler.
- LIVE API secret'ları veritabanına **asla açık metin olarak yazılmaz**; loglarda ve API yanıtlarında maskelenir.
- Güvenlik başlıkları (`X-Frame-Options`, `X-Content-Type-Options`, HSTS vb.) tüm yanıtlara otomatik eklenir.
- Tüm kritik admin aksiyonları (mod değişimi, manuel pozisyon kapatma, ayar değişikliği) denetim (audit) logunda saklanır.

## Sorun Giderme

- **API'ye giriş yapılamıyor:** `.env` içindeki `ADMIN_EMAIL`/`ADMIN_PASSWORD` ile `create_admin.py` scriptini çalıştırdığınızdan emin olun; veritabanının doğru `DATABASE_URL`'e işaret ettiğini kontrol edin.
- **Worker pozisyon açmıyor:** Bot Kontrol sayfasından botun `bot_enabled=true` ve `auto_trading_enabled=true` olduğundan, Semboller sayfasında ilgili sembolün kara listede olmadığından emin olun; Loglar sayfasındaki risk olaylarını inceleyin.
- **LIVE moda geçilemiyor:** `.env`'de `ENABLE_LIVE_TRADING=true` olduğundan ve Binance API anahtarınızın işlem (futures trade) iznine sahip olduğundan emin olun; panel size engelin tam nedenini gösterir.
- **Docker Compose'da `migrate` servisi hata veriyor:** PostgreSQL container'ının `healthy` durumuna geçmesini bekleyin (`docker compose logs postgres`); ardından `docker compose up -d --build` komutunu tekrar çalıştırın.
