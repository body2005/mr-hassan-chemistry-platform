param(
    [switch]$BuildOnly,
    [switch]$CheckOnly,
    [string]$ApiBaseImage = 'chemistry-video-api-pc:local'
)
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskEnvPath = Join-Path $taskRoot '.env.video-worker.local'
$taskTemplate = Join-Path $taskRoot 'infra/video-worker.pc.env.example'
$taskCompose = Join-Path $taskRoot 'infra/video-worker.pc.yml'

if (-not (Test-Path -LiteralPath $taskEnvPath)) {
    $taskSecretBytes = New-Object byte[] 48
    $taskRng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $taskRng.GetBytes($taskSecretBytes) } finally { $taskRng.Dispose() }
    $taskGeneratedSecret = [Convert]::ToBase64String($taskSecretBytes)
    $taskContent = [IO.File]::ReadAllText($taskTemplate).Replace('GENERATED_BY_START_SCRIPT', $taskGeneratedSecret)
    [IO.File]::WriteAllText($taskEnvPath, $taskContent, (New-Object Text.UTF8Encoding($false)))
    Write-Host "Created private configuration: $taskEnvPath"
}
& docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with its Linux engine first.' }

if ($BuildOnly) {
    & docker image inspect $ApiBaseImage --format '{{.Id}}' 2>$null
    if ($LASTEXITCODE -ne 0) {
        & docker build -f (Join-Path $taskRoot 'infra/Dockerfile.api') -t $ApiBaseImage (Join-Path $taskRoot 'apps/api')
        if ($LASTEXITCODE -ne 0) { throw 'API base image build failed.' }
    }
    $taskPreviousBase = $env:API_VIDEO_IMAGE
    try {
        $env:API_VIDEO_IMAGE = $ApiBaseImage
        & docker compose -p chemistry-video-pc -f $taskCompose build video-worker
        if ($LASTEXITCODE -ne 0) { throw 'Video worker image build failed.' }
    } finally { $env:API_VIDEO_IMAGE = $taskPreviousBase }
    Write-Host 'Worker image built. Configure storage/database, then run this script without -BuildOnly.'
    exit 0
}

# Check prerequisites before starting a persistent worker or enabling Render jobs.
& docker compose -p chemistry-video-pc -f $taskCompose run --rm --no-deps video-worker python -m scripts.video_worker_preflight
if ($LASTEXITCODE -ne 0) {
    throw "Worker not started. Complete $taskEnvPath and check prerequisites. Do not enable VIDEO_PROCESSING_ENABLED on Render yet."
}
if ($CheckOnly) { exit 0 }
& docker compose -p chemistry-video-pc -f $taskCompose up -d --no-build video-worker
if ($LASTEXITCODE -ne 0) { throw 'Worker startup failed.' }
Write-Host 'Worker started. Now configure matching private storage on Render, then enable VIDEO_PROCESSING_ENABLED=true.'
Write-Host 'Keep Docker Desktop and the PC running; sleeping or shutting down pauses processing.'
