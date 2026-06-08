# Start MACE AI Academy backend — bind 0.0.0.0 so localhost/LAN proxies can reach the API.
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".\venv\Scripts\uvicorn.exe")) {
    Write-Error "Virtual env not found. Run: python -m venv venv && .\venv\Scripts\pip install -r backend\requirements.txt"
    exit 1
}

Write-Host "Starting backend on http://127.0.0.1:8000  (docs: http://127.0.0.1:8000/docs)" -ForegroundColor Green
Write-Host "Use this window only — do not run: python -m uvicorn (system Python lacks dependencies)." -ForegroundColor Yellow
Write-Host "First chat message may take 1-3 min while the embedding model loads." -ForegroundColor Yellow

& ".\venv\Scripts\uvicorn.exe" backend.app:app --reload --host 0.0.0.0 --port 8000
