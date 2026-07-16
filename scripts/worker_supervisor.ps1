# Worker supervisor — cokerse otomatik yeniden baslatir.
$ErrorActionPreference = "Continue"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$WorkerDir = Join-Path $Root "services\worker"
$RunDir = Join-Path $Root ".run"
$LogFile = Join-Path $RunDir "worker_supervisor.log"
$SupervisorPidFile = Join-Path $RunDir "supervisor.pid"
$WorkerOutLog = Join-Path $RunDir "worker_stdout.log"
$WorkerErrLog = Join-Path $RunDir "worker_stderr.log"

if (-not (Test-Path $Python)) {
    Write-Error ".venv bulunamadi: $Python"
    exit 1
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Write-SupervisorLog {
    param([string]$Message)
    $line = "{0} | {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

Set-Content -Path $SupervisorPidFile -Value $PID -Encoding utf8
Write-SupervisorLog "Supervisor basladi (PID $PID)"

$backoffSec = 2
while ($true) {
    Write-SupervisorLog "Worker baslatiliyor..."
    $proc = Start-Process -FilePath $Python `
        -ArgumentList "-m", "worker.main" `
        -WorkingDirectory $WorkerDir `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $WorkerOutLog `
        -RedirectStandardError $WorkerErrLog `
        -Wait

    $exitCode = if ($null -ne $proc.ExitCode) { $proc.ExitCode } else { -1 }
    Write-SupervisorLog "Worker kapandi (exit=$exitCode). ${backoffSec}s sonra yeniden baslatiliyor..."
    Start-Sleep -Seconds $backoffSec
    $backoffSec = [Math]::Min($backoffSec * 2, 30)
}
