[CmdletBinding()]
param(
    [switch]$Volumes
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ($Volumes) {
    Write-Warning "CAUTION: This will delete all persistent named volumes (database, redis, minio)."
    $confirm = Read-Host "Type 'YES' to confirm volume deletion"
    if ($confirm -eq "YES") {
        docker compose -f compose.prod-like.yml down -v
    } else {
        Write-Host "Volume deletion cancelled. Stopping containers safely..." -ForegroundColor Yellow
        docker compose -f compose.prod-like.yml down
    }
} else {
    Write-Host "Stopping all production-like containers (preserving volumes)..." -ForegroundColor Cyan
    docker compose -f compose.prod-like.yml down
}
