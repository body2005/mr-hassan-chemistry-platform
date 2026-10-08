param(
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe',
    [ValidateSet('chemistryaudit2')][string]$Project = 'chemistryaudit2'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$env:VIDEO_UPLOAD_PUBLIC_ENDPOINT = 'https://localhost:18544'
$env:VIDEO_UPLOAD_PORT = '18544'
$env:VIDEO_UPLOAD_BIND = '127.0.0.1'
if (!(Test-Path '.qa/audit2/media/video.webm') -or !(Test-Path '.qa/audit2/media/large.pdf')) {
    throw 'Generate synthetic media with prepare-media.ps1 first'
}
$owner = & $Docker inspect "$Project-api-1" --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
if ($LASTEXITCODE -ne 0 -or $owner -ne "$Project/api") { throw 'Not the explicitly isolated QA runtime' }
$compose = @('compose','--env-file','.qa/audit2/compose.env','-p',$Project,
    '-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml','-f','infra/video-pipeline.override.yml')
# Never run this against a real production database or alongside browser tests.
# Only QA identities and new synthetic resources are added; volumes are retained.
# Seed from the disposable APP_ENV=test runner, never weakening the API's
# production startup guard to permit demo accounts or password resets.
& $Docker @compose run --rm --no-deps -e QA_ISOLATED=true qa-tests python scripts/seed_qa.py
if ($LASTEXITCODE -ne 0) { throw 'Synthetic account preparation failed' }
& $Docker @compose run --rm --no-deps -v "${taskRoot}/apps/api/tests:/srv/tests:ro" qa-tests python -m scripts.storage_drill checkpoint
if ($LASTEXITCODE -ne 0) { throw 'Synthetic storage checkpoint failed' }
