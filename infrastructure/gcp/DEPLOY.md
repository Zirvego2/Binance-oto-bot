# Google Cloud Run Deploy Rehberi

## Tek Servis (Onerilen - binance-bot-4446e)

Tum bilesenler (API + Worker + Web + Nginx) **tek Cloud Run servisinde** calisir:

```powershell
.\infrastructure\gcp\deploy-one.ps1
# Sadece yeniden deploy (build atla):
.\infrastructure\gcp\deploy-one.ps1 -SkipBuild
```

**Canli URL:** https://black-crypto-ai-bot-628342247496.europe-west1.run.app

---

Bu rehber **Black Crypto AI Bot** projesini **zirvego100@gmail.com** Google hesabi uzerinden Cloud Run'a deploy etmek icin hazirlanmistir.

## Mimari

```
                    ┌─────────────────┐
  Kullanicilar ───► │  bcai-web       │  Next.js panel (Cloud Run)
                    └────────┬────────┘
                             │ HTTPS API cagrilari
                    ┌────────▼────────┐
                    │  bcai-api       │  FastAPI + WebSocket (Cloud Run)
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
  ┌──────▼──────┐    ┌───────▼───────┐   ┌──────▼──────┐
  │ bcai-worker │    │ Cloud SQL     │   │ Redis       │
  │ (Cloud Run) │    │ PostgreSQL 16 │   │ Memorystore │
  └─────────────┘    └───────────────┘   └─────────────┘
```

- **3 Cloud Run servisi:** API, Web, Worker
- **1 Cloud Run Job:** Alembic migration (`bcai-migrate`)
- **SQLite kullanilmaz** — production icin PostgreSQL zorunlu
- **Worker** `min-instances=1` ile 7/24 calisir

---

## Onkosullar

1. [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install) kurulu
2. Faturalandirma acik bir GCP projesi
3. Firebase projesi (musteri girisi icin) — mevcut `binance-bot-4446e` kullanilabilir
4. Binance API anahtarlari (demo/live mod icin)

---

## Adim 1 — GCP hesabi ve proje

```powershell
# Ilk kurulum (proje ID'nizi yazin)
.\infrastructure\gcp\setup.ps1 -ProjectId "SIZIN-PROJE-ID"
```

Bu script:
- `zirvego100@gmail.com` ile giris yapar
- Gerekli API'leri acar (Run, Build, Artifact Registry, SQL, Secret Manager)
- `bcai` Artifact Registry reposunu olusturur

---

## Adim 2 — Cloud SQL (PostgreSQL)

```powershell
gcloud sql instances create bcai-db `
  --database-version=POSTGRES_16 `
  --tier=db-f1-micro `
  --region=europe-west1 `
  --storage-auto-increase

gcloud sql databases create bcai --instance=bcai-db
gcloud sql users create bcai_user --instance=bcai-db --password="GUCLU-SIFRE"
```

Connection name (env.gcp icin):
```
PROJE-ID:europe-west1:bcai-db
```

DATABASE_URL ornegi:
```
postgresql+asyncpg://bcai_user:GUCLU-SIFRE@/bcai?host=/cloudsql/PROJE-ID:europe-west1:bcai-db
```

---

## Adim 3 — Redis

**Secenek A — Memorystore (VPC gerekir, production icin onerilir)**

**Secenek B — Upstash (hizli baslangic)**

Upstash'ten Redis URL alin ve `REDIS_URL` olarak env.gcp'ye yazin.

> Worker ve API Redis olmadan dagitik kilit/rate-limit calistiramaz.

---

## Adim 4 — Secret Manager (Firebase)

Firebase service account JSON dosyasini Secret Manager'a yukleyin:

```powershell
gcloud secrets create firebase-sa-json --data-file=binance-bot-4446e-firebase-adminsdk-XXXX.json
```

Deploy scripti bunu `FIREBASE_SERVICE_ACCOUNT_JSON` olarak API ve Worker'a baglar.

Alternatif: env.gcp icinde `FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}` (tek satir JSON).

---

## Adim 5 — Ortam dosyasi

```powershell
Copy-Item infrastructure\gcp\env.gcp.example infrastructure\gcp\env.gcp
# env.gcp dosyasini duzenleyin (GERCEK degerler, git'e eklemeyin)
```

Kritik alanlar:
| Degisken | Aciklama |
|----------|----------|
| `GCP_PROJECT_ID` | GCP proje ID |
| `CLOUDSQL_INSTANCE` | `proje:bolge:instance` |
| `DATABASE_URL` | Cloud SQL socket URL |
| `REDIS_URL` | Redis baglanti |
| `APP_SECRET` / `APP_ENCRYPTION_KEY` | Guclu rastgele degerler |
| `SECURE_COOKIES=true` | HTTPS zorunlu |
| `FIREBASE_PROJECT_ID` | Firebase proje ID |
| `NEXT_PUBLIC_FIREBASE_*` | Web panel Firebase client |

---

## Adim 6 — Ilk deploy (API once)

Ilk deploy'da web build arg'lari icin API URL henuz bilinmiyor. Iki asamali deploy:

### 6a — API + Worker + Migration

```powershell
.\infrastructure\gcp\deploy.ps1 -WebOnly:$false
# veya sadece API:
.\infrastructure\gcp\deploy.ps1 -ApiOnly
```

API URL'ini alin:
```powershell
gcloud run services describe bcai-api --region europe-west1 --format="value(status.url)"
```

### 6b — env.gcp guncelle

```env
WEB_ORIGIN=https://bcai-web-....run.app
API_ORIGIN=https://bcai-api-....run.app
NEXT_PUBLIC_API_BASE_URL=https://bcai-api-....run.app/api/v1
NEXT_PUBLIC_WS_BASE_URL=wss://bcai-api-....run.app/api/v1
```

### 6c — Web rebuild + tam deploy

```powershell
.\infrastructure\gcp\deploy.ps1
```

---

## Adim 7 — Firebase Auth domain

Firebase Console → Authentication → Authorized domains:
- `bcai-web-....run.app` ekleyin

---

## Adim 8 — Dogrulama

| Kontrol | URL / Komut |
|---------|-------------|
| API health | `https://bcai-api-....run.app/api/v1/health` |
| Web panel | `https://bcai-web-....run.app/login` |
| Worker health | Cloud Run console → bcai-worker → Logs |
| Migration | `gcloud run jobs executions list --job=bcai-migrate` |

---

## Guncelleme (yeni surum)

```powershell
git pull
.\infrastructure\gcp\deploy.ps1
```

---

## Maliyet ipuclari

- **Web:** `min-instances=0` (cold start kabul edilebilir)
- **API + Worker:** `min-instances=1` (bot surekliligi icin)
- Cloud SQL `db-f1-micro` baslangic icin yeterli; yuk arttikca scale edin
- `europe-west1` bolgesi Turkiye'ye yakin

---

## Sorun giderme

| Sorun | Cozum |
|-------|-------|
| CORS / cookie hatasi | `WEB_ORIGIN` ve `API_ORIGIN` Cloud Run URL'leri ile eslesmeli |
| Worker duruyor | Redis URL, Cloud SQL baglantisi, loglari kontrol edin |
| Firebase login calismiyor | Authorized domains + `NEXT_PUBLIC_FIREBASE_*` build arg'lari |
| Migration hatasi | `gcloud run jobs executions logs` ile job loglarina bakin |

---

## Dosya referansi

| Dosya | Amac |
|-------|------|
| `infrastructure/gcp/cloudbuild.yaml` | 3 image build + push |
| `infrastructure/gcp/deploy.ps1` | Cloud Run deploy otomasyonu |
| `infrastructure/gcp/setup.ps1` | Ilk GCP kurulumu |
| `infrastructure/gcp/env.gcp.example` | Ortam sablonu |
| `services/api/Dockerfile` | API image (PORT=8080) |
| `services/worker/Dockerfile` | Worker image + /health |
| `apps/web/Dockerfile` | Next.js standalone |
