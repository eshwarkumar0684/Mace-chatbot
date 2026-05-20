# Start MACE AI Academy backend — bind 0.0.0.0 so localhost/LAN proxies can reach the API.
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".\venv\Scripts\uvicorn.exe")) {
    Write-Error "Virtual env not found. Run: python -m venv venv && .\venv\Scripts\pip install -r backend\requirements.txt"
    exit 1
}

Write-Host "Starting backend on http://0.0.0.0:8000  (reachable at http://127.0.0.1:8000)  Docs: http://127.0.0.1:8000/docs" -ForegroundColor Green

& ".\venv\Scripts\uvicorn.exe" backend.app:app --reload --host 0.0.0.0 --port 8000
