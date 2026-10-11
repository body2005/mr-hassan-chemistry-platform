param(
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe',
    [ValidateSet('chemistryaudit2','chemistryprodlocal')][string]$Project = 'chemistryaudit2'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$target = "$Project-video-worker-1"
$owner = & $Docker inspect $target --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
if ($LASTEXITCODE -ne 0 -or $owner -ne "$Project/video-worker") { throw 'Not the expected isolated encoder runtime' }
$image = & $Docker inspect $target --format '{{.Image}}'
if ($LASTEXITCODE -ne 0 -or $image -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Actual encoder image identity unavailable' }
# No application environment, signed links or logs are displayed. Fixed CLI
# checks use the runtime's non-root user and never change its files or media.
$source = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'verify-native-video.py') -Raw
$output = $source | & $Docker exec -i $target python -
$code = $LASTEXITCODE
$checks = $output | ConvertFrom-Json
$record = @{ image = $image; exit_code = $code; checks = $checks; utc = [DateTime]::UtcNow.ToString('o') }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$folder = if ($Project -eq 'chemistryaudit2') { 'audit2' } else { 'production' }
$record | ConvertTo-Json -Depth 7 | Tee-Object -FilePath (Join-Path $taskRoot ".qa/$folder/native-video-$stamp.json")
if ($code -ne 0) { throw "Actual native encoder checks failed (Exit Code $code); raw scanner findings remain separate." }
