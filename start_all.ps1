# Start backend + frontend (run from project root)
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".\venv\Scripts\uvicorn.exe")) {
    Write-Error "Virtual env missing. Run: python -m venv venv; .\venv\Scripts\pip install -r backend\requirements.txt"
    exit 1
}

Write-Host "Starting backend in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$ProjectRoot\start_backend.ps1"

Write-Host "Waiting for API on http://127.0.0.1:8000/health ..." -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
        if ($h.status) {
            $ready = $true
            Write-Host "Backend ready ($($h.status))." -ForegroundColor Green
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Warning "Backend did not respond in 90s. Check the backend window for errors, then refresh the chat."
}

Write-Host "Starting frontend..." -ForegroundColor Cyan
& "$ProjectRoot\start_frontend.ps1"
