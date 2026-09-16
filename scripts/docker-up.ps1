[CmdletBinding()]
param()

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "=== Starting Production-Like Local Docker Environment ===" -ForegroundColor Cyan

if (-not (Test-Path ".env.docker.local")) {
    Write-Host "Creating .env.docker.local from .env.docker.example..." -ForegroundColor Yellow
    Copy-Item ".env.docker.example" ".env.docker.local"
}

docker compose --env-file .env.docker.local -f compose.prod-like.yml config --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error "Compose configuration validation failed."
    exit 1
}

Write-Host "Building and launching containers..." -ForegroundColor Green
docker compose --env-file .env.docker.local -f compose.prod-like.yml up -d --build

Write-Host "`nContainer Status:" -ForegroundColor Cyan
docker compose --env-file .env.docker.local -f compose.prod-like.yml ps

Write-Host "`nPlatform URLs:" -ForegroundColor Green
Write-Host "  Frontend:  http://localhost:8080"
Write-Host "  Backend:   http://localhost:8000"
Write-Host "  API Docs:  http://localhost:8000/docs"
Write-Host "  MinIO:     http://localhost:9001 (minioadmin / miniopassword)"
