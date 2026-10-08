param(
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe',
    [ValidateSet('chemistryprodlocal','chemistryaudit2')][string]$Project = 'chemistryaudit2'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$folder = if ($Project -eq 'chemistryaudit2') { 'audit2' } else { 'production' }
$uploadPort = if ($Project -eq 'chemistryaudit2') { 18544 } else { 18444 }
$env:VIDEO_UPLOAD_PUBLIC_ENDPOINT = "https://localhost:$uploadPort"
$env:VIDEO_UPLOAD_PORT = "$uploadPort"
$env:VIDEO_UPLOAD_BIND = '127.0.0.1'
$media = Join-Path $taskRoot ".qa/$folder/media"
New-Item -ItemType Directory -Force -Path $media | Out-Null
$compose = @('compose','--env-file',".qa/$folder/compose.env",'-p',$Project,
    '-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml','-f','infra/video-pipeline.override.yml')
# Full FFmpeg is confined to a disposable fixture generator. The production
# encoder intentionally does not include libvpx or other unused decoders.
& $Docker build -f infra/qa/Dockerfile.media -t "$Project-media-fixtures" infra/qa
if ($LASTEXITCODE -ne 0) { throw 'Synthetic fixture generator build failed' }
& $Docker run --rm -v "${media}:/qa-media" "$Project-media-fixtures" `
    -hide_banner -loglevel error -y -f lavfi -i 'testsrc2=size=1280x720:rate=25' `
    -f lavfi -i 'sine=frequency=440:sample_rate=48000' -t 90 -c:v libvpx-vp9 -deadline realtime -cpu-used 8 -b:v 4M -minrate 4M -maxrate 4M -c:a libopus /qa-media/video.webm
if ($LASTEXITCODE -ne 0) { throw 'Synthetic video generation failed' }
# The resumable-upload journey interrupts part 2 (32 MiB parts). A short
# fixture would silently stop exercising multipart recovery, so fail early.
$videoSize = (Get-Item -LiteralPath (Join-Path $media 'video.webm')).Length
if ($videoSize -le 32MB -or $videoSize -ge 128MB) {
    throw "Synthetic video must be >32 MiB and <128 MiB for multipart QA; got $videoSize bytes"
}
& $Docker @compose run --rm --no-deps qa-tests python -m scripts.generate_qa_pdf
if ($LASTEXITCODE -ne 0) { throw 'Synthetic PDF generation failed' }
Get-ChildItem -LiteralPath $media -File | Select-Object Name,Length
