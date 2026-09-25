[CmdletBinding()]
param()

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "=== Running Docker Health and Integration Verification ===" -ForegroundColor Cyan

Write-Host "`n1. Checking Container Health:" -ForegroundColor Yellow
docker compose -f compose.prod-like.yml ps

Write-Host "`n2. Checking API Liveness (/health):" -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -Method Get -TimeoutSec 5
    Write-Host "  /health: OK -> $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Error "  /health failed: $_"
}

Write-Host "`n3. Checking API Readiness (/ready):" -ForegroundColor Yellow
try {
    $ready = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/ready" -Method Get -TimeoutSec 10
    Write-Host "  /ready: OK -> $($ready | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Warning "  /ready returned status code (check dependencies): $_"
}

Write-Host "`n4. Running Test Suite inside API Container:" -ForegroundColor Yellow
docker compose -f compose.prod-like.yml exec api python -m pytest tests/test_health.py tests/test_extraction_contract.py -v
