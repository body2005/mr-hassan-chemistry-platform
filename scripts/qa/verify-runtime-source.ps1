param([string]$Docker='C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$manifestCode=@'
import hashlib,json,pathlib
root=pathlib.Path('/srv')
files=[*root.joinpath('app').rglob('*.py'),root/'scripts/video_worker.py',root/'entrypoint-prod.sh']
print(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))
'@
$results=[System.Collections.Generic.List[object]]::new()
foreach($service in @('api','video-worker')){
    $target="chemistryaudit2-$service-1"
    $owner=& $Docker inspect $target --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
    if($LASTEXITCODE -ne 0 -or $owner -ne "chemistryaudit2/$service"){throw 'Not the expected isolated QA runtime'}
    $output=& $Docker exec $target python -c $manifestCode
    if($LASTEXITCODE -ne 0){throw 'Could not read runtime source manifest'}
    $manifest=$output | ConvertFrom-Json -AsHashtable
    $mismatch=[System.Collections.Generic.List[string]]::new()
    foreach($relative in $manifest.Keys){
        $file=Join-Path (Join-Path $taskRoot 'apps/api') $relative
        if(!(Test-Path -LiteralPath $file) -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest[$relative]){
            $mismatch.Add($relative)
        }
    }
    $hostSources=@(rg --files apps/api/app -g '*.py')
    foreach($file in $hostSources){
        $relative=$file.Replace('\','/').Substring('apps/api/'.Length)
        if(!$manifest.ContainsKey($relative)){$mismatch.Add("missing-in-runtime:$relative")}
    }
    $image=& $Docker inspect $target --format '{{.Image}}'
    $record=@{service=$service;image=$image;compared_files=$manifest.Count;mismatches=@($mismatch)}
    $results.Add($record)
    $record | ConvertTo-Json -Depth 4
    if($mismatch.Count -gt 0){throw 'Runtime code differs from the working tree; rebuild and retest before claiming a final gate'}
}
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ".qa/audit2/runtime-source-$stamp.json" -Encoding utf8
