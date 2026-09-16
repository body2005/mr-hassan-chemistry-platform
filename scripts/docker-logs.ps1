[CmdletBinding()]
param(
    [string]$Service = "",
    [int]$Tail = 100,
    [switch]$Follow
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$cmdArgs = @("-f", "compose.prod-like.yml", "logs", "--tail", $Tail)
if ($Follow) {
    $cmdArgs += "-f"
}
if ($Service) {
    $cmdArgs += $Service
}

docker compose @cmdArgs
