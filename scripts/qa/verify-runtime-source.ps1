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
# Browser stage must first run npm build from this working tree. Check the
# served bytes, not just an image tag: Compose can leave an older web image.
$webTarget='chemistryaudit2-web-1'
$webOwner=& $Docker inspect $webTarget --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
if($LASTEXITCODE -ne 0 -or $webOwner -ne 'chemistryaudit2/web'){throw 'Not the expected isolated QA web runtime'}
$webImage=& $Docker inspect $webTarget --format '{{.Image}}'
$builtWebImage=& $Docker image inspect chemistryaudit2-web --format '{{.Id}}'
if($LASTEXITCODE -ne 0 -or $webImage -ne $builtWebImage){throw 'Web container does not run the latest built image; recreate it and retest'}
$webOutput=& $Docker exec $webTarget sh -c 'cd /usr/share/nginx/html && find . -type f -exec sha256sum {} \;'
if($LASTEXITCODE -ne 0){throw 'Could not read served web asset hashes'}
$webManifest=@{}
foreach($line in $webOutput){
    if($line -notmatch '^([a-f0-9]{64})  \./(.+)$'){throw 'Invalid web asset manifest'}
    $webManifest[$Matches[2]]=$Matches[1]
}
$webMismatch=[System.Collections.Generic.List[string]]::new()
$webDist=Join-Path $taskRoot 'apps/web/dist'
if(!(Test-Path -LiteralPath (Join-Path $webDist 'index.html'))){throw 'Run the Browser gate/npm build before checking web byte equivalence'}
$webFiles=@(Get-ChildItem -LiteralPath $webDist -Recurse -File)
foreach($file in $webFiles){
    $relative=$file.FullName.Substring($webDist.Length+1).Replace('\','/')
    if(!$webManifest.ContainsKey($relative) -or (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $webManifest[$relative]){
        $webMismatch.Add($relative)
    }
}
foreach($relative in $webManifest.Keys){
    # 50x.html is nginx's base-image error page, not an application asset.
    if($relative -ne '50x.html' -and !(Test-Path -LiteralPath (Join-Path $webDist $relative))){$webMismatch.Add("unexpected-runtime-asset:$relative")}
}
$webConfig=& $Docker exec $webTarget sha256sum /etc/nginx/conf.d/default.conf
if($LASTEXITCODE -ne 0 -or $webConfig.Split(' ')[0] -ne (Get-FileHash -LiteralPath (Join-Path $taskRoot 'apps/web/nginx.conf') -Algorithm SHA256).Hash.ToLowerInvariant()){
    $webMismatch.Add('nginx.conf')
}
$webRecord=@{service='web';image=$webImage;compared_files=$webFiles.Count+1;mismatches=@($webMismatch);method='fresh host build vs served assets and nginx config'}
$results.Add($webRecord)
$webRecord | ConvertTo-Json -Depth 4
if($webMismatch.Count -gt 0){throw 'Served web files differ from the current build; rebuild and retest'}
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ".qa/audit2/runtime-source-$stamp.json" -Encoding utf8
