$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$pythonPath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { $pythonPath = (Get-Command python -ErrorAction Stop).Source }
$running = $false
try { $health = Invoke-RestMethod 'http://127.0.0.1:8769/api/v2/health' -TimeoutSec 2; $running = $health.application -eq 'di-dashboard' } catch {}
if (-not $running) {
    $portOwner = Get-NetTCPConnection -LocalPort 8769 -State Listen -ErrorAction SilentlyContinue
    if ($portOwner) { throw 'Port 8769 is already used by another app. Stop that service before starting DI Dashboard.' }
    Start-Process -FilePath $pythonPath -ArgumentList @('server.py','--port','8769') -WorkingDirectory $appRoot -WindowStyle Hidden
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 250
        try { $health = Invoke-RestMethod 'http://127.0.0.1:8769/api/v2/health' -TimeoutSec 1; if ($health.application -eq 'di-dashboard') { $running = $true; break } } catch {}
    }
}
if (-not $running) { throw 'The dashboard could not start. Run server.py in a terminal to see the error.' }
Start-Process 'http://127.0.0.1:8769/'
