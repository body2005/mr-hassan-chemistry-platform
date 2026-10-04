param(
    [ValidateSet('chemistryaudit2','chemistryprodlocal')][string]$Project='chemistryaudit2',
    [string]$Docker='C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$folder=if($Project -eq 'chemistryaudit2'){'audit2'}else{'production'}
$env:VIDEO_UPLOAD_PUBLIC_ENDPOINT=if($Project -eq 'chemistryaudit2'){'https://localhost:18544'}else{'https://localhost:18444'}
$env:VIDEO_UPLOAD_PORT=if($Project -eq 'chemistryaudit2'){'18544'}else{'18444'}
$env:VIDEO_UPLOAD_BIND='127.0.0.1'
$env:QA_RESTORE_RUN_ID=([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8)).ToLowerInvariant()
$compose=@('compose','--env-file',".qa/$folder/compose.env",'-p',$Project,'-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml','-f','infra/video-pipeline.override.yml')
$restored=$compose+@('-f','infra/qa/video-restore.override.yml')
$results=[System.Collections.Generic.List[object]]::new()
# Freeze the image identity, not the shared source checkout (Extract may still
# be changing). Backup uses the actual production service/entrypoint/command.
$env:QA_BACKUP_IMAGE=& $Docker inspect "$Project-api-1" --format '{{.Image}}'
if($LASTEXITCODE -ne 0 -or $env:QA_BACKUP_IMAGE -notmatch '^sha256:[a-f0-9]{64}$'){
    throw 'Could not identify the tested API image; no backup rebuild attempted'
}
function Invoke-Drill([string]$Label,[string[]]$ArgsList,[switch]$Restore){
    $prefix=if($Restore){$restored}else{$compose}
    & $Docker @prefix @ArgsList
    $code=$LASTEXITCODE
    $results.Add(@{command=$Label;exit_code=$code;utc=[DateTime]::UtcNow.ToString('o')})
    $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath ".qa/$folder/video-storage-$($env:QA_RESTORE_RUN_ID).json" -Encoding utf8
    if($code -ne 0){throw "Storage drill '$Label' failed: Exit $code"}
}
$probe=@'
import os,time,requests
deadline=time.monotonic()+160
while time.monotonic()<deadline:
    try:
        r=requests.get('https://proxy/api/v1/ready',verify=os.environ['QA_CA_FILE'],timeout=(3,6))
        if r.status_code==200:
            print('Actual HTTPS readiness recovered'); break
    except requests.RequestException: pass
    time.sleep(1)
else: raise SystemExit('HTTPS readiness did not recover')
'@
Invoke-Drill 'validate video/storage template' @('config','-q')
Invoke-Drill 'validate restored application template' @('config','-q') -Restore
Invoke-Drill 'original assets and SHA-256' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.verify_video_assets')
Invoke-Drill 'legacy video/material/receipt and ownership checkpoint' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.storage_drill','verify')
$frozen=$false
$restoreStarted=$false
try{
    $frozen=$true
    Invoke-Drill 'freeze ALL ingress/application/encoder writers' @('stop','upload-gateway','api','worker','video-worker')
    Invoke-Drill 'recreate SeaweedFS WITHOUT removing volume' @('up','-d','--no-deps','--force-recreate','--wait','--wait-timeout','90','s3')
    Invoke-Drill 'original hashes/private reads after storage recreation' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.verify_video_assets')
    Invoke-Drill 'PostgreSQL snapshot' @('run','--rm','--no-deps','backup-postgres')
    # compose run has no --no-build flag. It does not build unless --build is
    # requested; the existing immutable image ID and pull=never are sufficient.
    Invoke-Drill 'production backup on SAME tested API image; no source rebuild' @('run','--rm','--no-deps','--pull','never','backup-s3')
    $snapshot=Get-ChildItem -LiteralPath ".qa/$folder/backups/s3" -Directory | Sort-Object Name | Select-Object -Last 1
    $dump=Get-ChildItem -LiteralPath ".qa/$folder/backups" -Filter 'postgres-*.dump' | Sort-Object Name | Select-Object -Last 1
    if(!$snapshot -or !(Test-Path (Join-Path $snapshot.FullName 'manifest.json')) -or !$dump){throw 'No completed matching backup artifacts'}
    $restoreStarted=$true
    Invoke-Drill 'NEW isolated PostgreSQL/SeaweedFS volumes' @('up','-d','--no-deps','--wait','--wait-timeout','90','s3-restore','postgres-restore')
    Invoke-Drill 'restore S3 + verify every object SHA-256 and metadata' @('run','--rm','--no-deps','-e','S3_ENDPOINT_URL=http://s3-restore:8333','qa-tests','python','scripts/s3_snapshot.py','restore','--snapshot',"/qa/backups/s3/$($snapshot.Name)")
    Invoke-Drill 'restore DB into EMPTY new target; no clean/drop' @('exec','-T','postgres-restore','pg_restore','--exit-on-error','--no-owner','--no-privileges','-U','lms','-d','restored',"/backups/$($dump.Name)")
    Invoke-Drill 'compare EVERY table and row before starting restored app' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.verify_db_restore')
    Invoke-Drill 'actual API/Celery/encoder/upload gateway on RESTORED DB and S3' @('up','-d','--no-deps','--force-recreate','--wait','--wait-timeout','160','worker','api','video-worker','upload-gateway') -Restore
    Invoke-Drill 'restored HTTPS readiness (trusted local CA)' @('run','--rm','--no-deps','qa-tests','python','-c',$probe) -Restore
    Invoke-Drill 'restored full originals/output existence/S3 privacy' @('run','--rm','--no-deps','qa-tests','python','/qa-tools/use-restored-db.py','python','-m','scripts.verify_video_assets') -Restore
    Invoke-Drill 'restored material/receipt/video/ranges/ownership via actual API' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.storage_drill','verify') -Restore
    Invoke-Drill 'restored HLS/Range/session-bound permissions via actual API' @('run','--rm','--no-deps','qa-tests','python','/qa-tools/use-restored-db.py','python','/qa-tools/verify-restored-hls.py') -Restore
    Invoke-Drill 'lost multipart recovery against restored DB/S3' @('run','--rm','--no-deps','qa-tests','python','/qa-tools/use-restored-db.py','python','/qa-tools/test-lost-multipart.py') -Restore
    # Real browser uploads NEW bytes through the restored upload gateway,
    # waits for the restored encoder, plays/seeks HLS, and checks revocation.
    $env:QA_BASE_URL=if($Project -eq 'chemistryaudit2'){'https://localhost:18543'}else{'https://localhost:18443'}
    $env:QA_LOCAL_TLS='true'
    $env:QA_REDIS_CONTAINER="$Project-redis-1"
    $env:QA_DOCKER=$Docker
    $env:QA_VIDEO_FILE=Join-Path $taskRoot ".qa/$folder/media/video.webm"
    $env:PLAYWRIGHT_JUNIT_OUTPUT_FILE=Join-Path $taskRoot ".qa/$folder/restored-video-$($env:QA_RESTORE_RUN_ID).xml"
    $env:QA_PLAYWRIGHT_OUTPUT=Join-Path $taskRoot ".qa/$folder/restored-video-$($env:QA_RESTORE_RUN_ID)"
    Push-Location (Join-Path $taskRoot 'apps/web')
    try{
        & npx.cmd playwright test --config playwright.qa.config.ts tests/qa/video-playback.spec.ts --reporter=list,junit
        $code=$LASTEXITCODE
        $results.Add(@{command='actual browser NEW upload/encode/playback on restored stores';exit_code=$code;utc=[DateTime]::UtcNow.ToString('o')})
        $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $taskRoot ".qa/$folder/video-storage-$($env:QA_RESTORE_RUN_ID).json") -Encoding utf8
        if($code -ne 0){throw "Restored browser failed: Exit $code"}
    }finally{Pop-Location}
}finally{
    if($frozen){
        Invoke-Drill 'return original DB/S3/ALL writer configuration' @('up','-d','--no-deps','--force-recreate','--wait','--wait-timeout','160','worker','video-worker','api','upload-gateway')
        Invoke-Drill 'original HTTPS readiness recovered' @('run','--rm','--no-deps','qa-tests','python','-c',$probe)
    }
    if($restoreStarted){Invoke-Drill 'stop disposable restore servers; PRESERVE volumes' @('stop','s3-restore','postgres-restore')}
}
Write-Output 'Completed on synthetic QA only. Original and restore volumes preserved; no external deployment.'
