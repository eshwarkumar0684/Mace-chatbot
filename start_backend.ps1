# Start MACE AI Academy backend (must run from project root)
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".\venv\Scripts\uvicorn.exe")) {
    Write-Error "Virtual env not found. Run: python -m venv venv && .\venv\Scripts\pip install -r backend\requirements.txt"
    exit 1
}

Write-Host "Starting backend at http://127.0.0.1:8000 (docs: /docs)" -ForegroundColor Green
& ".\venv\Scripts\uvicorn.exe" backend.app:app --reload --host 127.0.0.1 --port 8000
