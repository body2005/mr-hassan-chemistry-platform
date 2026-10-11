param(
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe',
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$qaRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $qaRoot
if (!(Test-Path '.qa/audit2/compose.env')) { throw 'Prepare and start the isolated chemistryaudit2 project first; see the role QA report.' }
$qaStamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$env:QA_BASE_URL = 'https://localhost:18543'
$env:QA_LOCAL_TLS = 'false'
$env:QA_REDIS_CONTAINER = 'chemistryaudit2-redis-1'
$env:QA_DOCKER = $Docker
$env:QA_PYTHON = $Python # Python with pypdf for inspecting the actual student PDF.
$env:QA_PLAYWRIGHT_OUTPUT = Join-Path $qaRoot ".qa/audit2/role-results-$qaStamp"
$env:PLAYWRIGHT_JUNIT_OUTPUT_FILE = Join-Path $qaRoot ".qa/audit2/role-browser-$qaStamp.xml"
$env:VIDEO_UPLOAD_PUBLIC_ENDPOINT = 'https://localhost:18544'
$env:VIDEO_UPLOAD_PORT = '18544'
$env:VIDEO_UPLOAD_BIND = '127.0.0.1'
$qaResults = [System.Collections.Generic.List[object]]::new()
function Save-RoleResult([string]$Label, [int]$Code) {
    $qaResults.Add(@{ command = $Label; exit_code = $Code; utc = [DateTime]::UtcNow.ToString('o') })
    $qaResults | ConvertTo-Json | Set-Content -LiteralPath ".qa/audit2/role-commands-$qaStamp.json" -Encoding utf8
}
& (Join-Path $PSHOME $(if($IsWindows){'pwsh.exe'}else{'pwsh'})) -NoProfile -File (Join-Path $PSScriptRoot 'run-trusted-browser.ps1') -Build -Docker $Docker -SpecPattern tests/qa/discovery.spec.ts
$qaBrowserExit = $LASTEXITCODE
Save-RoleResult 'teacher/student discovery (no expected-failure masking)' $qaBrowserExit
$qaCompose = @('compose', '--env-file', '.qa/audit2/compose.env', '-p', 'chemistryaudit2',
    '-f', 'infra/docker-compose.yml', '-f', 'infra/qa/production.override.yml', '-f', 'infra/video-pipeline.override.yml')
& $Docker @qaCompose run --rm --no-deps `
    -v "${qaRoot}/apps/api/scripts/qa_extract_fidelity.py:/srv/scripts/qa_extract_fidelity.py:ro" `
    -v "${qaRoot}/apps/api/tests/fixtures/blind_inputs:/srv/tests/fixtures/blind_inputs:ro" `
    qa-tests python -m scripts.qa_extract_fidelity --output "/qa/role-extract-$qaStamp.json"
$qaExtractExit = $LASTEXITCODE
Save-RoleResult 'strict Extract source fidelity (no parser edits)' $qaExtractExit
& git -c core.safecrlf=false diff --check
$qaDiffExit = $LASTEXITCODE
Save-RoleResult 'git diff --check' $qaDiffExit
if ($qaBrowserExit -ne 0 -or $qaExtractExit -ne 0 -or $qaDiffExit -ne 0) { exit 1 }
exit 0
