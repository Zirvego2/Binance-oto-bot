# Binance Bot - tek instance olarak baslat (worker + api)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error ".venv bulunamadi. Once: python -m venv .venv && pip install ..."
}

# Once hepsini durdur
& (Join-Path $PSScriptRoot "stop_bot.ps1")

# SQLite WAL
& $Python -c @"
import sqlite3
from pathlib import Path
db = Path(r'$Root') / 'trading_bot.db'
if db.exists():
    c = sqlite3.connect(db, timeout=60)
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA busy_timeout=60000')
    c.commit()
    c.close()
    print('SQLite WAL OK')
"@

Start-Process -FilePath $Python -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" `
    -WorkingDirectory (Join-Path $Root "services\api") -WindowStyle Hidden

Start-Sleep -Seconds 2

Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", (Join-Path $PSScriptRoot "worker_supervisor.ps1") `
    -WorkingDirectory $Root

Start-Sleep -Seconds 2

$WebDir = Join-Path $Root "apps\web"
$EnvLocal = Join-Path $WebDir ".env.local"
$EnvLocalExample = Join-Path $WebDir ".env.local.example"
if (-not (Test-Path $EnvLocal) -and (Test-Path $EnvLocalExample)) {
    Copy-Item $EnvLocalExample $EnvLocal
    Write-Host "  .env.local olusturuldu (apps/web/.env.local.example'dan)"
}

$Npm = Get-Command npm -ErrorAction SilentlyContinue
if ($Npm -and (Test-Path (Join-Path $WebDir "node_modules"))) {
    # 3000/3001 portlarinin bosalmasini bekle (eski Next.js surecleri)
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        $busy = netstat -ano | Select-String ":3000\s.*LISTENING|:3001\s.*LISTENING"
        if (-not $busy) { break }
        Start-Sleep -Seconds 1
    }

    Start-Process -FilePath "cmd.exe" -ArgumentList "/c","npm run dev" `
        -WorkingDirectory $WebDir -WindowStyle Hidden

    $ready = $false
    $waitDeadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $waitDeadline) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:3000/login" -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if ($ready) {
        Write-Host "  Web Panel: http://localhost:3000/login"
    } else {
        Write-Host "  Web Panel: baslatildi ama hazir olmayabilir - http://localhost:3000/login"
    }
} else {
    Write-Host "  Web Panel: ATLANADI (apps/web icinde npm install gerekli)"
}

Write-Host ""
Write-Host "Bot baslatildi (tek instance):"
Write-Host "  API:       http://127.0.0.1:8000"
Write-Host "  Worker:    supervisor (otomatik yeniden baslatma)"
if ($Npm -and (Test-Path (Join-Path $WebDir "node_modules"))) {
    Write-Host "  Panel:     http://localhost:3000/login"
}
Write-Host ""
Write-Host "Durdurmak icin: scripts\stop_bot.ps1"
