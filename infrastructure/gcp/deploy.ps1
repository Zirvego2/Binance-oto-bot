# Black Crypto AI Bot - Cloud Run deploy script
# Kullanim: .\infrastructure\gcp\deploy.ps1
param(
    [string]$EnvFile = "",
    [switch]$SkipBuild,
    [switch]$SkipMigrate,
    [switch]$ApiOnly,
    [switch]$WebOnly,
    [switch]$WorkerOnly
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $EnvFile) {
    $EnvFile = Join-Path $PSScriptRoot "env.gcp"
}

if (-not (Test-Path $EnvFile)) {
    Write-Error "Ortam dosyasi bulunamadi: $EnvFile`nOnce env.gcp.example dosyasini env.gcp olarak kopyalayin."
}

function Read-EnvFile([string]$Path) {
    $map = @{}
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

$envMap = Read-EnvFile $EnvFile
function Get-Env([string]$Key, [string]$Default = "") {
    if ($envMap.ContainsKey($Key) -and $envMap[$Key]) { return $envMap[$Key] }
    return $Default
}

$ProjectId = Get-Env "GCP_PROJECT_ID"
$Region = Get-Env "GCP_REGION" "europe-west1"
$Repo = Get-Env "ARTIFACT_REPO" "bcai"
$ServiceApi = Get-Env "SERVICE_API" "bcai-api"
$ServiceWeb = Get-Env "SERVICE_WEB" "bcai-web"
$ServiceWorker = Get-Env "SERVICE_WORKER" "bcai-worker"
$JobMigrate = Get-Env "JOB_MIGRATE" "bcai-migrate"
$CloudSql = Get-Env "CLOUDSQL_INSTANCE"

if (-not $ProjectId) { Write-Error "GCP_PROJECT_ID env.gcp icinde tanimli olmali" }

gcloud config set project $ProjectId | Out-Null
gcloud config set run/region $Region | Out-Null

$imageApi = "$Region-docker.pkg.dev/$ProjectId/$Repo/api:latest"
$imageWeb = "$Region-docker.pkg.dev/$ProjectId/$Repo/web:latest"
$imageWorker = "$Region-docker.pkg.dev/$ProjectId/$Repo/worker:latest"

if (-not $SkipBuild) {
    Write-Host "Cloud Build baslatiliyor..."
    $subs = @(
        "_REGION=$Region",
        "_ARTIFACT_REPO=$Repo",
        "_NEXT_PUBLIC_API_BASE_URL=$(Get-Env 'NEXT_PUBLIC_API_BASE_URL' '/api/v1')",
        "_NEXT_PUBLIC_WS_BASE_URL=$(Get-Env 'NEXT_PUBLIC_WS_BASE_URL' '/api/v1')",
        "_SESSION_COOKIE_NAME=$(Get-Env 'SESSION_COOKIE_NAME' 'trading_bot_session')",
        "_NEXT_PUBLIC_FIREBASE_API_KEY=$(Get-Env 'NEXT_PUBLIC_FIREBASE_API_KEY')",
        "_NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=$(Get-Env 'NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN')",
        "_NEXT_PUBLIC_FIREBASE_PROJECT_ID=$(Get-Env 'NEXT_PUBLIC_FIREBASE_PROJECT_ID')",
        "_NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=$(Get-Env 'NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET')",
        "_NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=$(Get-Env 'NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID')",
        "_NEXT_PUBLIC_FIREBASE_APP_ID=$(Get-Env 'NEXT_PUBLIC_FIREBASE_APP_ID')",
        "_API_PROXY_TARGET=$(Get-Env 'API_ORIGIN' '')"
    ) -join ","

    Push-Location $Root
    try {
        gcloud builds submit . `
            --config=infrastructure/gcp/cloudbuild.yaml `
            --substitutions=$subs
    } finally {
        Pop-Location
    }
}

function Build-RunEnvVars {
    $keys = @(
        "APP_ENV", "APP_SECRET", "APP_ENCRYPTION_KEY", "DATABASE_URL", "REDIS_URL",
        "BINANCE_ENV", "BINANCE_API_KEY", "BINANCE_API_SECRET",
        "ENABLE_DEMO_TRADING", "ENABLE_LIVE_TRADING", "MAX_ALLOWED_LEVERAGE",
        "WEB_ORIGIN", "API_ORIGIN", "SESSION_COOKIE_NAME", "SESSION_TTL_MINUTES",
        "SECURE_COOKIES", "LOG_LEVEL", "FIREBASE_PROJECT_ID",
        "OPENAI_API_KEY", "AI_MODEL", "AI_EXPLANATION_ENABLED",
        "EMERGENCY_CLOSE_PASSWORD", "PROFILE_ACCESS_PASSWORD"
    )
    $pairs = @("SKIP_PROCESS_LOCK=true")
    foreach ($key in $keys) {
        $val = Get-Env $key
        if ($val) { $pairs += "$key=$val" }
    }
    return ($pairs -join ",")
}

function Get-SecretEnvArgs {
    $args = @()
    if (Get-Env "FIREBASE_SERVICE_ACCOUNT_JSON") {
        $args += "--set-secrets=FIREBASE_SERVICE_ACCOUNT_JSON=firebase-sa-json:latest"
    }
    return $args
}

$runEnv = Build-RunEnvVars
$sqlArg = @()
if ($CloudSql) {
    $sqlArg = @("--add-cloudsql-instances=$CloudSql")
}

if (-not $WebOnly -and -not $WorkerOnly) {
    if (-not $SkipMigrate) {
        Write-Host "Migration job calistiriliyor..."
        gcloud run jobs deploy $JobMigrate `
            --image $imageApi `
            --region $Region `
            --command alembic `
            --args upgrade,head `
            --set-env-vars $runEnv `
            @sqlArg `
            --max-retries 1 `
            --task-timeout 600 `
            --quiet 2>$null

        gcloud run jobs execute $JobMigrate --region $Region --wait
    }

    Write-Host "API deploy ediliyor..."
    gcloud run deploy $ServiceApi `
        --image $imageApi `
        --region $Region `
        --platform managed `
        --allow-unauthenticated `
        --port 8080 `
        --cpu 1 `
        --memory 1Gi `
        --min-instances 1 `
        --max-instances 4 `
        --timeout 3600 `
        --concurrency 80 `
        --set-env-vars $runEnv `
        @sqlArg `
        (Get-SecretEnvArgs) `
        --quiet

    $apiUrl = gcloud run services describe $ServiceApi --region $Region --format="value(status.url)"
    Write-Host "API URL: $apiUrl"
}

if (-not $ApiOnly -and -not $WebOnly) {
    Write-Host "Worker deploy ediliyor..."
    gcloud run deploy $ServiceWorker `
        --image $imageWorker `
        --region $Region `
        --platform managed `
        --no-allow-unauthenticated `
        --port 8080 `
        --cpu 1 `
        --memory 1Gi `
        --min-instances 1 `
        --max-instances 1 `
        --timeout 3600 `
        --concurrency 1 `
        --set-env-vars $runEnv `
        @sqlArg `
        (Get-SecretEnvArgs) `
        --quiet
}

if (-not $ApiOnly -and -not $WorkerOnly) {
    Write-Host "Web deploy ediliyor..."
    gcloud run deploy $ServiceWeb `
        --image $imageWeb `
        --region $Region `
        --platform managed `
        --allow-unauthenticated `
        --port 8080 `
        --cpu 1 `
        --memory 512Mi `
        --min-instances 0 `
        --max-instances 4 `
        --set-env-vars "NODE_ENV=production" `
        --quiet

    $webUrl = gcloud run services describe $ServiceWeb --region $Region --format="value(status.url)"
    Write-Host "Web URL: $webUrl"
}

Write-Host ""
Write-Host "Deploy tamamlandi."
Write-Host "Onemli: WEB_ORIGIN ve API_ORIGIN degerlerini Cloud Run URL'leri ile env.gcp'de guncelleyip API'yi yeniden deploy edin."
