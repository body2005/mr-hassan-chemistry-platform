param(
    [ValidateSet('Build','Backend','Tests','Integration','Browser','Recovery','Assets','Load','Scan','All')][string]$Stage = 'All',
    [ValidateSet('chemistryprodlocal','chemistryaudit2')][string]$Project = 'chemistryaudit2',
    [switch]$ApproveScout,
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$folder = if ($Project -eq 'chemistryaudit2') { 'audit2' } else { 'production' }
$httpsPort = if ($Project -eq 'chemistryaudit2') { 18543 } else { 18443 }
$mailPort = if ($Project -eq 'chemistryaudit2') { 18525 } else { 18425 }
$uploadPort = if ($Project -eq 'chemistryaudit2') { 18544 } else { 18444 }
$env:VIDEO_UPLOAD_PUBLIC_ENDPOINT = "https://localhost:$uploadPort"
$env:VIDEO_UPLOAD_PORT = "$uploadPort"
$env:VIDEO_UPLOAD_BIND = '127.0.0.1'
$compose = @('compose','--env-file',".qa/$folder/compose.env",'-p',$Project,
    '-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml','-f','infra/video-pipeline.override.yml')
$results = [System.Collections.Generic.List[object]]::new()
$runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$npmExecutable = if ($IsWindows) { 'npm.cmd' } else { 'npm' }
$npxExecutable = if ($IsWindows) { 'npx.cmd' } else { 'npx' }
function Save-Results {
    $json = $results | ConvertTo-Json -Depth 4
    $json | Set-Content -LiteralPath (Join-Path $taskRoot ".qa/$folder/video-commands-$Stage-$runId.json") -Encoding utf8
    $json | Set-Content -LiteralPath (Join-Path $taskRoot ".qa/$folder/video-commands-$Stage.json") -Encoding utf8
}
function Invoke-Step([string]$Label, [string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    $code = $LASTEXITCODE
    $results.Add(@{command=$Label; exit_code=$code; utc=[DateTime]::UtcNow.ToString('o')})
    Save-Results
    if ($code -ne 0) { throw "Video gate '$Label' failed (Exit Code $code). No deployment/push performed." }
}
if (!(Test-Path ".qa/$folder/compose.env")) { throw 'Run prepare-production.ps1 for this isolated project first.' }
if ($Stage -eq 'Scan') {
    if (!$ApproveScout) { throw 'Docker Scout shares image/SBOM package metadata externally. Obtain approval, then pass -ApproveScout.' }
    $scanFailed = $false
    foreach ($image in @('api','video-worker')) {
        $target = "$Project-$image-1"
        $owner = & $Docker inspect $target --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
        if ($LASTEXITCODE -ne 0 -or $owner -ne "$Project/$image") { throw 'Scan target is not the expected isolated runtime' }
        $runtimeImage = & $Docker inspect $target --format '{{.Image}}'
        if ($LASTEXITCODE -ne 0 -or $runtimeImage -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Could not identify the actual tested image' }
        & $Docker image inspect $runtimeImage --format '{{.Id}}' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Runtime image manifest is no longer inspectable. Recreate from the intended built image, retest, then scan; do not substitute a mutable tag.' }
        # A new BuildKit attestation/tag can differ while Compose retains the
        # same payload container. Scan its actual identity, not a mutable tag.
        & $Docker scout cves "local://$runtimeImage" --only-severity critical,high --format sarif --output ".qa/$folder/scout-video-$image-$runId.sarif" --exit-code
        $code = $LASTEXITCODE
        $results.Add(@{command="Docker Scout $image $runtimeImage (critical/high gate)"; exit_code=$code; utc=[DateTime]::UtcNow.ToString('o')})
        Save-Results
        if ($code -ne 0) { $scanFailed = $true }
    }
    if ($scanFailed) { throw 'Security gate is open. Review both SARIF files; do not suppress findings to obtain a zero exit code.' }
}
if ($Stage -eq 'Assets') {
    Invoke-Step 'original SHA-256/output existence/private S3 checks' $Docker ($compose + @('run','--rm','--no-deps','qa-tests','python','-m','scripts.verify_video_assets'))
}
if ($Stage -eq 'Load') {
    # Mount the current QA tool read-only; the application images remain the
    # tested build. Do not overlap this with fault/restore/browser suites.
    Invoke-Step '3 x 180s real HLS/browsing/large PDF mixed load' $Docker ($compose + @('run','--rm','--no-deps','-v',"${taskRoot}/apps/api/scripts/qa_load.py:/srv/scripts/qa_load.py:ro",'qa-tests','python','-m','scripts.qa_load'))
}
if ($Stage -eq 'Integration') {
    . (Join-Path $PSScriptRoot 'runtime-recovery.ps1')
    $baseline = @(Get-QARuntimeSnapshot -Docker $Docker -Project $Project)
    try {
        Invoke-Step 'all live PostgreSQL/storage/fault integration tests' $Docker ($compose + @('run','--rm','--no-deps','-v',"${taskRoot}/apps/api/tests:/srv/tests:ro",'-e','STORAGE_DIR=/tmp/qa-storage','qa-tests','python','-m','pytest','tests/integration','-q','--tb=short',"--junitxml=/qa/api-integration-video-$runId.xml",'-o','junit_logging=all'))
    } finally {
        try {
            $recovery = @(Restore-QARuntimeSnapshot -Docker $Docker -Snapshot $baseline)
            $recovery | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath ".qa/$folder/runtime-recovery-$runId.json" -Encoding utf8
            $results.Add(@{command='restore initially running QA services after fault runner exit (not readiness)';exit_code=0;utc=[DateTime]::UtcNow.ToString('o')})
        } catch {
            $results.Add(@{command='restore initially running QA services after fault runner exit (not readiness)';exit_code=1;utc=[DateTime]::UtcNow.ToString('o')})
            throw
        } finally { Save-Results }
    }
}
if ($Stage -eq 'Recovery') {
    Invoke-Step 'stopped encoder and real crash during encoding with PostgreSQL durable retry' $Docker ($compose + @('run','--rm','--no-deps','-e','PYTHONPATH=/srv','-v',"${taskRoot}/infra/qa:/qa-tools:ro",'qa-tests','python','/qa-tools/video-worker-recovery.py'))
}
if ($Stage -in @('Build','All')) {
    Invoke-Step 'video compose validation' $Docker ($compose + @('config','-q'))
    Invoke-Step 'API/migration/Celery/web/staging-permissions build' $Docker ($compose + @('build','api','migration','worker','web','upload-permissions'))
    # Explicit sequencing avoids extending the old API in a parallel build.
    Invoke-Step 'video worker / QA build' $Docker ($compose + @('build','video-worker','qa-tests'))
    # Compose can keep an older manifest identity when BuildKit changes only
    # the attestation. Recreate the selected runtime services after a build;
    # named data volumes are retained, and the source gate verifies the IDs.
    Invoke-Step 'local video pipeline startup' $Docker ($compose + @('up','-d','--no-build','--force-recreate','--wait','--wait-timeout','160','migration','s3-init','api','worker','web','proxy','video-worker','upload-gateway'))
}
if ($Stage -in @('Backend','Tests','All')) {
    foreach ($nativeService in @('api','video-worker')) {
        Invoke-Step "native/Python Expat UTF-16 and buffer-capacity security regressions ($nativeService)" $Docker ($compose + @('exec','-T',$nativeService,'python','-m','scripts.verify_native_expat'))
    }
    $qaShellExecutable = Join-Path $PSHOME $(if ($IsWindows) { 'pwsh.exe' } else { 'pwsh' })
    Invoke-Step 'actual restricted FFmpeg binary and signed provenance checks' $qaShellExecutable @('-NoProfile','-File',(Join-Path $PSScriptRoot 'verify-native-video.ps1'),'-Docker',$Docker,'-Project',$Project)
    Invoke-Step 'API unit and protection tests' $Docker ($compose + @('run','--rm','--no-deps','-v',"${taskRoot}/render.yaml:/qa-tools/render.yaml:ro",'-v',"${taskRoot}/apps/api/tests:/srv/tests:ro",'-e','STORAGE_DIR=/tmp/qa-storage','qa-tests','python','-m','pytest','tests','--ignore=tests/integration','-q',"--junitxml=/qa/api-unit-video-$runId.xml"))
    Invoke-Step 'fresh/previous-head PostgreSQL migration gates' $Docker ($compose + @('run','--rm','--no-deps','qa-tests','python','-m','scripts.ci_migrations'))
    Invoke-Step 'real PostgreSQL/S3 missing multipart recovery' $Docker ($compose + @('run','--rm','--no-deps','-e','PYTHONPATH=/srv','-v',"${taskRoot}/infra/qa:/qa-tools:ro",'qa-tests','python','/qa-tools/test-lost-multipart.py'))
}
if ($Stage -in @('Tests','Browser','All')) {
    if ($Stage -eq 'Browser') {
        # Browser tests must run the current served frontend, not an older
        # image that happens to pass while npm builds different local assets.
        # Only web/proxy are recreated; API, data and real limits are retained.
        Invoke-Step 'build current served frontend before full browser gate' $Docker ($compose + @('build','web'))
        Invoke-Step 'recreate current web/proxy only' $Docker ($compose + @('up','-d','--no-deps','--no-build','--force-recreate','--wait','--wait-timeout','90','web','proxy'))
    }
    Invoke-Step 'start isolated QA SMTP inbox' $Docker ($compose + @('up','-d','--no-deps','mailpit'))
    $mailReady = $false
    $mailDeadline = [DateTime]::UtcNow.AddSeconds(30)
    while ([DateTime]::UtcNow -lt $mailDeadline) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$mailPort/readyz" -TimeoutSec 3
            if ($response.StatusCode -eq 200) { $mailReady = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    $results.Add(@{command='QA SMTP inbox readiness'; exit_code=$(if ($mailReady) { 0 } else { 1 }); utc=[DateTime]::UtcNow.ToString('o')})
    Save-Results
    if (!$mailReady) { throw 'QA SMTP inbox is unavailable; do not skip the reset-email tests.' }
    $env:QA_BASE_URL = "https://localhost:$httpsPort"
    $env:QA_LOCAL_TLS = 'true'
    $env:QA_MAILPIT_URL = "http://127.0.0.1:$mailPort"
    $env:QA_REDIS_CONTAINER = "$Project-redis-1"
    $env:QA_DOCKER = $Docker
    $env:QA_MEDIA_DIR = Join-Path $taskRoot ".qa/$folder/media"
    $env:QA_VIDEO_FILE = Join-Path $env:QA_MEDIA_DIR 'video.webm'
    # Match the production Docker build, not a developer's .env.local API URL.
    # This also makes served-asset/source hash verification meaningful.
    $env:VITE_API_URL = '/api/v1'
    $env:PLAYWRIGHT_JUNIT_OUTPUT_FILE = Join-Path $taskRoot ".qa/$folder/video-browser-$Stage-$runId.xml"
    $env:QA_PLAYWRIGHT_OUTPUT = Join-Path $taskRoot (".qa/$folder/video-results-" + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
    Push-Location (Join-Path $taskRoot 'apps/web')
    try {
        Invoke-Step 'frontend lint' $npmExecutable @('run','lint')
        Invoke-Step 'frontend build' $npmExecutable @('run','build')
        # Run every isolated file with one fork on memory-constrained local
        # hosts. This does not skip tests or change assertions/security limits.
        $frontendResults = Join-Path $taskRoot ".qa/$folder/frontend-video-$runId.xml"
        Invoke-Step 'frontend unit tests' $npmExecutable @('test','--','--maxWorkers=1',
            '--reporter=default','--reporter=junit',"--outputFile=$frontendResults")
        if ($Stage -eq 'Browser') {
            Invoke-Step 'all frontend browser journeys on production template' $npxExecutable @('playwright','test','--config','playwright.qa.config.ts','--reporter=list,junit')
            Invoke-Step 'npm dependency audit' $npmExecutable @('audit','--audit-level=high')
        } else {
            Invoke-Step 'publication/resumption/playback browser tests' $npxExecutable @('playwright','test','--config','playwright.qa.config.ts','tests/qa/publication.spec.ts','tests/qa/video-playback.spec.ts','--reporter=list,junit')
        }
    } finally { Pop-Location }
    Invoke-Step 'diff check' 'git' @('-c','core.safecrlf=false','diff','--check')
}
