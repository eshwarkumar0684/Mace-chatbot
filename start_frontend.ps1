# Start MACE AI Academy frontend (requires Node.js in PATH)
$env:Path = "C:\Program Files\nodejs;" + $env:Path
$ProjectRoot = $PSScriptRoot
Set-Location (Join-Path $ProjectRoot "frontend")

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "npm not found. Install Node.js from https://nodejs.org/ and restart your terminal."
    exit 1
}

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    npm install
}

Write-Host "Starting frontend at http://localhost:3000" -ForegroundColor Green
npm run dev
