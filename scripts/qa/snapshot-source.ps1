# Detect changes during a long QA gate; never substitute this for runtime byte checks.
param(
    [ValidateSet('Snapshot','Verify')][string]$Mode='Snapshot',
    [string]$Manifest
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
if(!$Manifest){
    if($Mode -eq 'Verify'){throw 'Verify requires the exact preceding manifest path'}
    $Manifest=Join-Path $taskRoot ".qa/audit2/source-snapshot-$stamp.json"
}
$manifestPath=[IO.Path]::GetFullPath($Manifest, $taskRoot)
$privateRoot=Join-Path $taskRoot '.qa'
if(!$manifestPath.StartsWith($privateRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){
    throw 'QA source evidence must be saved inside this project .qa directory'
}
$roots=@('apps/api/app','apps/api/scripts','apps/api/tests','apps/web/src','apps/web/tests','apps/web/scripts','infra','scripts/qa','.github')
# rg honors ignore files: private fixtures/runtime storage/build caches are not exported.
$paths=@(rg --files @roots -g '!__pycache__/**' -g '!*.pyc' -g '!*.env' -g '!*.pem' -g '!*.key' `
    -g '!apps/api/tests/load/*_results*.csv' -g '!apps/api/tests/load/locust_users.json')
if($LASTEXITCODE -ne 0){throw 'Cannot enumerate the source scope'}
$paths+=@('apps/api/entrypoint-prod.sh','apps/api/requirements.txt','apps/api/requirements.lock',
    'apps/api/pyproject.toml','apps/web/package.json','apps/web/package-lock.json',
    'apps/web/playwright.qa.config.ts','apps/web/vitest.config.ts','apps/web/vite.config.ts',
    'apps/web/tsconfig.json','apps/web/tsconfig.app.json','apps/web/nginx.conf','render.yaml')
$hashes=@{}
foreach($relative in @($paths | Sort-Object -Unique)){
    $path=Join-Path $taskRoot $relative
    if(Test-Path -LiteralPath $path -PathType Leaf){
        $hashes[$relative.Replace('\','/')]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
if($Mode -eq 'Snapshot'){
    $head=git rev-parse HEAD
    if($LASTEXITCODE -ne 0){throw 'Cannot identify local HEAD'}
    @{schema=1;utc=[DateTime]::UtcNow.ToString('o');head=$head;files=$hashes} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8
    Write-Output "Source snapshot: $manifestPath; $($hashes.Count) files. Runtime/data/docs and unrelated projects excluded."
    exit 0
}
$before=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -AsHashtable
if($before.schema -ne 1 -or !$before.files){throw 'Invalid QA source snapshot'}
$changed=@()
foreach($relative in @(@($before.files.Keys)+@($hashes.Keys) | Sort-Object -Unique)){
    if($before.files[$relative] -ne $hashes[$relative]){$changed+=$relative}
}
$head=git rev-parse HEAD
if($LASTEXITCODE -ne 0){throw 'Cannot verify local HEAD'}
$result=@{manifest=$manifestPath;compared_files=$hashes.Count;head_changed=($before.head -ne $head);
    changed_files=$changed;utc=[DateTime]::UtcNow.ToString('o')}
$result | ConvertTo-Json -Depth 5 | Tee-Object -FilePath (Join-Path $privateRoot "audit2/source-verification-$stamp.json")
if($changed.Count -gt 0 -or $result.head_changed){exit 1}
exit 0
