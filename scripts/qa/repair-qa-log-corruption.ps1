param([string]$Docker='C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
# This maintenance action is intentionally restricted to this disposable QA
# project; it does not inspect/recreate containers belonging to other projects.
$project='chemistryaudit2'
$env:VIDEO_UPLOAD_PUBLIC_ENDPOINT='https://localhost:18544'
$env:VIDEO_UPLOAD_PORT='18544'
$compose=@('compose','--env-file','.qa/audit2/compose.env','-p',$project,'-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml','-f','infra/video-pipeline.override.yml')
$results=[System.Collections.Generic.List[object]]::new()
$services=@('postgres','redis','s3','worker','video-worker','api','web','proxy','upload-gateway','mailpit')
$broken=[System.Collections.Generic.List[string]]::new()
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
foreach($service in $services){
    $container="$project-$service-1"
    $identity=& $Docker inspect $container --format '{{.Id}}'
    if($LASTEXITCODE -ne 0){throw "Missing QA service $service"}
    $owner=& $Docker inspect $container --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
    if($LASTEXITCODE -ne 0 -or $owner -ne "$project/$service"){throw "Unexpected ownership of $container"}
    $log=& $Docker inspect $container --format '{{.LogPath}}'
    if($LASTEXITCODE -ne 0 -or $log -ne "/var/lib/docker/containers/$identity/$identity-json.log"){
        throw "Expected exact json-file path for QA service $service; no repair attempted"
    }
    $prefix=@('run','--rm','--network','none','--read-only','-e','QA_ISOLATED=true','-e',"QA_PROJECT=$project",
        '-v',"${log}:/source-log:ro",'-v',"${taskRoot}/.qa/audit2:/qa",'-v',"${taskRoot}/infra/qa:/qa-tools:ro",
        '--entrypoint','python',"$project-api",'/qa-tools/inspect-log-file.py','--service',$service)
    $output=& $Docker @prefix --inspect-only
    if($LASTEXITCODE -ne 0){throw "Inspection failed for $service"}
    $record=$output | ConvertFrom-Json
    $results.Add($record)
    $results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath ".qa/audit2/log-inspection-$stamp.json" -Encoding utf8
    Write-Output "$service : malformed_records=$($record.bad_count), bytes=$($record.bytes)"
    if($record.bad_count -gt 0){
        $broken.Add($service)
        & $Docker @compose stop $service
        if($LASTEXITCODE -ne 0){throw "Could not freeze $service"}
        try{
            & $Docker @prefix
            if($LASTEXITCODE -ne 0){throw "Could not archive $service log"}
        }finally{
            # Never edit/truncate the daemon's file. Its forensic copy is kept
            # under ignored .qa; recreate only this container, preserving volumes.
            & $Docker @compose up -d --no-deps --force-recreate --wait --wait-timeout 160 $service
            if($LASTEXITCODE -ne 0){throw "QA service $service recovery failed"}
        }
    }
}
Write-Output "Recreated malformed-log QA services only: $($broken -join ', '). All volumes preserved."
