param([string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$compose = @('compose','--env-file','.qa/production/compose.env','-p','chemistryprodlocal','-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml')
function Invoke-QaCompose([string[]]$Arguments) {
    & $Docker @compose @Arguments
    if ($LASTEXITCODE -ne 0) { throw "QA Compose failed (exit $LASTEXITCODE): $Arguments" }
}
# Worker startup and proxy DNS recovery are asynchronous. Wait for actual
# readiness, not a fixed sleep or liveness alone. Never accept degraded/503.
$readinessProbe = @'
import os, requests, time
deadline = time.monotonic() + 160
last_status = None
while time.monotonic() < deadline:
    try:
        response = requests.get("https://proxy/api/v1/ready", verify=os.environ["QA_CA_FILE"], timeout=(3, 6))
        last_status = response.status_code
        if last_status == 200:
            print("Verified HTTPS readiness recovered")
            break
    except requests.RequestException:
        last_status = "connection_error"
    time.sleep(1)
else:
    raise SystemExit(f"HTTPS readiness deadline exceeded; last status={last_status}")
'@
Invoke-QaCompose @('run','--rm','--no-deps','qa-tests','python','-m','scripts.storage_drill','verify')
# Recreate storage, database and API WITHOUT removing volumes or touching the old project.
Invoke-QaCompose @('up','-d','--no-deps','--force-recreate','postgres','s3')
Invoke-QaCompose @('up','-d','--no-deps','--force-recreate','api')
Invoke-QaCompose @('up','-d','--wait','--wait-timeout','160')
Invoke-QaCompose @('run','--rm','--no-deps','qa-tests','python','-m','scripts.storage_drill','verify')
# Freeze writers for a consistent cross-store snapshot; restore only to NEW stores.
Invoke-QaCompose @('stop','api','worker')
try {
    Invoke-QaCompose @('run','--rm','--no-deps','backup-postgres')
    Invoke-QaCompose @('run','--rm','--no-deps','--build','backup-s3')
    Invoke-QaCompose @('run','--rm','--no-deps','--build','backup-videos')
    $snapshot = Get-ChildItem -LiteralPath '.qa/production/backups/s3' -Directory | Sort-Object Name | Select-Object -Last 1
    if (!$snapshot -or !(Test-Path (Join-Path $snapshot.FullName 'manifest.json'))) { throw 'No completed snapshot found' }
    # Same bucket NAME on a completely NEW server/volume: stored s3:// paths
    # remain valid. Distinct volume names make the drill repeatable safely.
    $bucket = 'chemistry-production-qa'
    $env:QA_RESTORE_RUN_ID = $snapshot.Name.ToLowerInvariant()
    $dump = Get-ChildItem -LiteralPath '.qa/production/backups' -Filter 'postgres-*.dump' | Sort-Object Name | Select-Object -Last 1
    Invoke-QaCompose @('up','-d','--wait','--wait-timeout','90','s3-restore','postgres-restore')
    Invoke-QaCompose @('run','--rm','--no-deps','-e','S3_ENDPOINT_URL=http://s3-restore:8333','-e',"S3_BUCKET=$bucket",'qa-tests','python','scripts/s3_snapshot.py','restore','--snapshot',"/qa/backups/s3/$($snapshot.Name)")
    # No clean/drop flags; a used restore target must be reviewed, not overwritten.
    Invoke-QaCompose @('exec','-T','postgres-restore','pg_restore','--exit-on-error','--no-owner','--no-privileges','-U','lms','-d','restored',"/backups/$($dump.Name)")
    Invoke-QaCompose @('run','--rm','--no-deps','qa-tests','python','-m','scripts.verify_db_restore')
    Invoke-QaCompose @('up','-d','--no-deps','--wait','--wait-timeout','160','worker')
    $restoreOverlay = Join-Path $taskRoot '.qa/production/restore-app.override.yml'
    [IO.File]::WriteAllText($restoreOverlay, "services:`n  api:`n    environment:`n      S3_ENDPOINT_URL: http://s3-restore:8333`n")
    & $Docker @compose -f $restoreOverlay up -d --no-deps --force-recreate api
    if ($LASTEXITCODE -ne 0) { throw 'Could not test API on restored storage' }
    # Explicitly trust the locally generated certificate, not a blanket TLS bypass.
    Invoke-QaCompose @('run','--rm','--no-deps','qa-tests','python','-c',$readinessProbe)
    Invoke-QaCompose @('run','--rm','--no-deps','-e','S3_ENDPOINT_URL=http://s3-restore:8333','-e',"S3_BUCKET=$bucket",'qa-tests','python','-m','scripts.storage_drill','verify')
} finally {
    Invoke-QaCompose @('up','-d','--no-deps','--force-recreate','api')
    Invoke-QaCompose @('up','-d','--wait','--wait-timeout','160')
    Invoke-QaCompose @('run','--rm','--no-deps','qa-tests','python','-c',$readinessProbe)
    Invoke-QaCompose @('stop','s3-restore','postgres-restore')
}
Write-Output 'Production storage persistence and backup/restore drill completed. Originals preserved.'
