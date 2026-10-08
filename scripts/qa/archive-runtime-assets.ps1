param([switch]$VerifyOnly, [string]$Manifest)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
if ($VerifyOnly) {
    if (!$Manifest) { throw 'Specify the archived inventory JSON' }
    $inventory = Get-Content -Raw -LiteralPath $Manifest | ConvertFrom-Json
    foreach ($row in $inventory.files) {
        $file = Join-Path $taskRoot $row.path
        if (!(Test-Path -LiteralPath $file) -or (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash -ne $row.sha256) {
            throw "Original runtime asset changed or missing: $($row.path)"
        }
    }
    Write-Output "Originals retained: $($inventory.files.Count), hashes match."
    exit 0
}
$names = @(git -c core.quotepath=false ls-files -- apps/api/storage)
if ($LASTEXITCODE -ne 0 -or !$names.Count) { throw 'No tracked runtime assets to inventory' }
$archiveDir = Join-Path $taskRoot ('.qa/runtime-assets/' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $archiveDir | Out-Null
$files = foreach ($name in $names) {
    $file = Get-Item -LiteralPath (Join-Path $taskRoot $name)
    if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Archive requires ordinary contained files, not links' }
    [pscustomobject]@{path=$name;bytes=$file.Length;sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash}
}
$list = Join-Path $archiveDir 'paths.txt'
[IO.File]::WriteAllLines($list, $names, [Text.UTF8Encoding]::new($false))
$archive = Join-Path $archiveDir 'storage.tar'
tar -cf $archive -T $list
if ($LASTEXITCODE -ne 0) { throw 'Archive creation failed; do not untrack assets' }
$restored = Join-Path $archiveDir 'verification'
New-Item -ItemType Directory -Path $restored | Out-Null
tar -xf $archive -C $restored
if ($LASTEXITCODE -ne 0) { throw 'Archive verification extraction failed' }
foreach ($row in $files) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $restored $row.path)).Hash -ne $row.sha256) {
        throw "Archive hash mismatch: $($row.path)"
    }
}
$inventory = @{ files=$files;archive=$archive;archive_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash;
    bytes=($files | Measure-Object bytes -Sum).Sum; head=(git rev-parse HEAD); utc=[DateTime]::UtcNow.ToString('o') }
$inventory | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $archiveDir 'inventory.json') -Encoding utf8
Write-Output "Verified archive and $($files.Count) originals: $archiveDir"
# This tool NEVER deletes or untracks originals. Review the inventory first,
# then use git rm --cached only for this exact runtime directory.
