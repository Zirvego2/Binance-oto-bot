# Tek Cloud Run servisi deploy (binance-bot-4446e)
# Kullanim: .\infrastructure\gcp\deploy-one.ps1

param(
    [string]$ProjectId = "binance-bot-4446e",
    [string]$Region = "europe-west1",
    [string]$ServiceName = "black-crypto-ai-bot",
    [string]$ArtifactRepo = "bcai",
    [string]$SqlInstance = "bcai-db",
    [string]$RootEnvFile = "",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $RootEnvFile) { $RootEnvFile = Join-Path $Root ".env" }

function Read-EnvFile([string]$Path) {
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        $map[$key] = $val
    }
    return $map
}

function Get-Val($map, [string]$Key, [string]$Default = "") {
    if ($map.ContainsKey($Key) -and $map[$Key]) { return $map[$Key] }
    return $Default
}

$envMap = Read-EnvFile $RootEnvFile
$webLocal = Read-EnvFile (Join-Path $Root "apps\web\.env.local")

Write-Host "Proje: $ProjectId | Servis: $ServiceName | Bolge: $Region"
gcloud config set project $ProjectId | Out-Null
gcloud config set run/region $Region | Out-Null

Write-Host "API'ler etkinlestiriliyor..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com sqladmin.googleapis.com --quiet | Out-Null

# Artifact Registry
$ErrorActionPreference = "Continue"
$repoCheck = gcloud artifacts repositories describe $ArtifactRepo --location=$Region 2>&1
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Artifact Registry olusturuluyor: $ArtifactRepo"
    gcloud artifacts repositories create $ArtifactRepo --repository-format=docker --location=$Region --description="Black Crypto AI Bot"
}

# Cloud SQL
$ErrorActionPreference = "Continue"
$sqlList = gcloud sql instances list --format="value(name)" 2>&1
$ErrorActionPreference = "Stop"
if ($sqlList -notcontains $SqlInstance) {
    $dbPass = -join ((48..57 + 65..90 + 97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    Write-Host "Cloud SQL olusturuluyor: $SqlInstance (5-10 dk surebilir)..."
    gcloud sql instances create $SqlInstance `
        --database-version=POSTGRES_16 `
        --edition=enterprise `
        --tier=db-f1-micro `
        --region=$Region `
        --root-password=$dbPass `
        --storage-auto-increase `
        --quiet
    gcloud sql databases create bcai --instance=$SqlInstance --quiet
    gcloud sql users create bcai_user --instance=$SqlInstance --password=$dbPass --quiet

    # Sifreyi Secret Manager'a kaydet
    $dbUrl = "postgresql+asyncpg://bcai_user:${dbPass}@/bcai?host=/cloudsql/${ProjectId}:${Region}:${SqlInstance}"
    $tmpSecret = Join-Path $env:TEMP "bcai-database-url.txt"
    [System.IO.File]::WriteAllText($tmpSecret, $dbUrl)
    $ErrorActionPreference = "Continue"
    gcloud secrets create bcai-database-url --data-file=$tmpSecret 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        gcloud secrets versions add bcai-database-url --data-file=$tmpSecret
    }
    $ErrorActionPreference = "Stop"
    Remove-Item $tmpSecret -Force -ErrorAction SilentlyContinue
    Write-Host "Cloud SQL hazir."
} else {
    Write-Host "Cloud SQL mevcut: $SqlInstance"
    $ErrorActionPreference = "Continue"
    gcloud secrets describe bcai-database-url 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Cloud SQL var ama bcai-database-url secret yok. Secret Manager'da DATABASE_URL olusturun."
    }
}

# Firebase secret
$firebaseJsonPath = Join-Path $Root "binance-bot-4446e-firebase-adminsdk-fbsvc-e327598f56.json"
if (Test-Path $firebaseJsonPath) {
    $ErrorActionPreference = "Continue"
    gcloud secrets describe firebase-sa-json 2>&1 | Out-Null
    $secretExists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = "Stop"
    if (-not $secretExists) {
        gcloud secrets create firebase-sa-json --data-file=$firebaseJsonPath
    } else {
        gcloud secrets versions add firebase-sa-json --data-file=$firebaseJsonPath
    }
}

# Cloud Build - tek image
$image = "${Region}-docker.pkg.dev/${ProjectId}/${ArtifactRepo}/all-in-one:latest"
Write-Host "Image build ediliyor (Cloud Build)..."

$subs = @(
    "_REGION=$Region",
    "_ARTIFACT_REPO=$ArtifactRepo",
    "_NEXT_PUBLIC_API_BASE_URL=/api/v1",
    "_NEXT_PUBLIC_WS_BASE_URL=/api/v1",
    "_NEXT_PUBLIC_SESSION_COOKIE_NAME=$(Get-Val $envMap 'SESSION_COOKIE_NAME' 'trading_bot_session')",
    "_NEXT_PUBLIC_FIREBASE_API_KEY=$(Get-Val $webLocal 'NEXT_PUBLIC_FIREBASE_API_KEY')",
    "_NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=$(Get-Val $webLocal 'NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN')",
    "_NEXT_PUBLIC_FIREBASE_PROJECT_ID=$(Get-Val $webLocal 'NEXT_PUBLIC_FIREBASE_PROJECT_ID' $ProjectId)",
    "_NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=$(Get-Val $webLocal 'NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET')",
    "_NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=$(Get-Val $webLocal 'NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID')",
    "_NEXT_PUBLIC_FIREBASE_APP_ID=$(Get-Val $webLocal 'NEXT_PUBLIC_FIREBASE_APP_ID')"
) -join ","

if (-not $SkipBuild) {
    Push-Location $Root
    try {
        gcloud builds submit . `
            --config=infrastructure/gcp/cloudbuild-one.yaml `
            --substitutions=$subs
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Cloud Build basarisiz. Log: gcloud builds log --project=$ProjectId"
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Build atlandi (-SkipBuild)."
}

# Deploy URL placeholder - guncellenecek
$cloudSqlConn = "${ProjectId}:${Region}:${SqlInstance}"

# Env vars (hassas olmayanlar)
$runEnv = @(
    "APP_ENV=production",
    "SECURE_COOKIES=true",
    "SKIP_PROCESS_LOCK=true",
    "FIREBASE_PROJECT_ID=$(Get-Val $envMap 'FIREBASE_PROJECT_ID' $ProjectId)",
    "BINANCE_ENV=$(Get-Val $envMap 'BINANCE_ENV' 'paper')",
    "ENABLE_DEMO_TRADING=$(Get-Val $envMap 'ENABLE_DEMO_TRADING' 'false')",
    "ENABLE_LIVE_TRADING=$(Get-Val $envMap 'ENABLE_LIVE_TRADING' 'false')",
    "LOG_LEVEL=INFO",
    "REDIS_URL=$(Get-Val $envMap 'REDIS_URL')",
    "SESSION_COOKIE_NAME=$(Get-Val $envMap 'SESSION_COOKIE_NAME' 'trading_bot_session')",
    "SESSION_TTL_MINUTES=$(Get-Val $envMap 'SESSION_TTL_MINUTES' '480')",
    "OPENAI_API_KEY=$(Get-Val $envMap 'OPENAI_API_KEY')",
    "AI_EXPLANATION_ENABLED=$(Get-Val $envMap 'AI_EXPLANATION_ENABLED' 'true')",
    "AI_MODEL=$(Get-Val $envMap 'AI_MODEL' 'gpt-4o-mini')",
    "TELEGRAM_NOTIFICATIONS_ENABLED=$(Get-Val $envMap 'TELEGRAM_NOTIFICATIONS_ENABLED' 'false')",
    "TELEGRAM_BOT_TOKEN=$(Get-Val $envMap 'TELEGRAM_BOT_TOKEN')",
    "TELEGRAM_CHAT_ID=$(Get-Val $envMap 'TELEGRAM_CHAT_ID')",
    "EMERGENCY_CLOSE_PASSWORD=$(Get-Val $envMap 'EMERGENCY_CLOSE_PASSWORD' '1453')",
    "PROFILE_ACCESS_PASSWORD=$(Get-Val $envMap 'PROFILE_ACCESS_PASSWORD' '14531453')",
    "ADMIN_EMAIL=$(Get-Val $envMap 'ADMIN_EMAIL' 'admin@example.com')",
    "ADMIN_PASSWORD=$(Get-Val $envMap 'ADMIN_PASSWORD' 'ChangeMe123!')",
    "BINANCE_API_KEY=$(Get-Val $envMap 'BINANCE_API_KEY')",
    "BINANCE_API_SECRET=$(Get-Val $envMap 'BINANCE_API_SECRET')",
    "APP_SECRET=$(Get-Val $envMap 'APP_SECRET')",
    "APP_ENCRYPTION_KEY=$(Get-Val $envMap 'APP_ENCRYPTION_KEY')"
) -join ","

Write-Host "Cloud Run deploy ediliyor: $ServiceName ..."

$projectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"
$runSa = "${projectNumber}-compute@developer.gserviceaccount.com"
$ErrorActionPreference = "Continue"
foreach ($secret in @("bcai-database-url", "firebase-sa-json")) {
    gcloud secrets add-iam-policy-binding $secret `
        --member="serviceAccount:$runSa" `
        --role="roles/secretmanager.secretAccessor" `
        --quiet 2>&1 | Out-Null
}
gcloud projects add-iam-policy-binding $ProjectId `
    --member="serviceAccount:$runSa" `
    --role="roles/cloudsql.client" `
    --quiet 2>&1 | Out-Null
$ErrorActionPreference = "Stop"

gcloud run deploy $ServiceName `
    --image $image `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --port 8080 `
    --cpu 2 `
    --memory 2Gi `
    --min-instances 1 `
    --max-instances 2 `
    --timeout 3600 `
    --concurrency 80 `
    --add-cloudsql-instances $cloudSqlConn `
    --set-secrets "DATABASE_URL=bcai-database-url:latest,FIREBASE_SERVICE_ACCOUNT_JSON=firebase-sa-json:latest" `
    --set-env-vars $runEnv `
    --quiet

$serviceUrl = gcloud run services describe $ServiceName --region $Region --format="value(status.url)"
Write-Host ""
Write-Host "Deploy tamamlandi!"
Write-Host "URL: $serviceUrl"
Write-Host ""
Write-Host "Son adim: WEB_ORIGIN ve API_ORIGIN guncelleme"
gcloud run services update $ServiceName `
    --region $Region `
    --update-env-vars "WEB_ORIGIN=$serviceUrl,API_ORIGIN=$serviceUrl" `
    --quiet

Write-Host "Panel: ${serviceUrl}/login"
