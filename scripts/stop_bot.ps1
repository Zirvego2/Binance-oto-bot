# Binance Bot - tum servisleri temiz durdur
$ErrorActionPreference = "SilentlyContinue"

# Supervisor once durdurulmali; aksi halde worker'i yeniden baslatir
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -match 'worker_supervisor\.ps1' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1

function Stop-PortListeners {
    param([int]$Port)
    netstat -ano | Select-String ":$Port\s.*LISTENING" | ForEach-Object {
        $listenerPid = ($_.Line -split '\s+')[-1]
        if ($listenerPid -match '^\d+$' -and [int]$listenerPid -gt 0) {
            Stop-Process -Id ([int]$listenerPid) -Force -ErrorAction SilentlyContinue
        }
    }
}

foreach ($port in 3000, 3001, 8000, 8080) {
    Stop-PortListeners -Port $port
}

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'worker\.main|uvicorn.*app\.main' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1

# .venv disi kopyalar (eski manuel baslatmalar)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {
        $_.CommandLine -match 'worker\.main|uvicorn.*app\.main' -and
        $_.CommandLine -notmatch '\\\.venv\\Scripts\\python\.exe'
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -match 'worker_supervisor\.ps1' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -match 'next dev|next start|apps\\web|apps/web' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" |
    Where-Object { $_.CommandLine -match 'npm run dev' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 3

$runDir = Join-Path $PSScriptRoot "..\.run"
if (Test-Path $runDir) {
    Remove-Item "$runDir\*.pid" -Force -ErrorAction SilentlyContinue
}

Write-Host "Bot servisleri durduruldu."
