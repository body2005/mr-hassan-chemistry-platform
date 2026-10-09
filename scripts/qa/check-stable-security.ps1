param(
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$results = [System.Collections.Generic.List[object]]::new()
foreach ($service in @('api', 'video-worker')) {
    $name = "chemistryaudit2-$service-1"
    $owner = & $Docker inspect $name --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
    if ($LASTEXITCODE -ne 0 -or $owner -ne "chemistryaudit2/$service") { throw 'Unexpected security check target' }
    $image = & $Docker inspect $name --format '{{.Image}}'
    if ($LASTEXITCODE -ne 0 -or $image -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Missing immutable runtime identity' }
    # No runtime container mutation or application secrets. Root is ONLY in
    # the disposable package-query container; current runtime UID is unchanged.
    # Refresh official stable/security indexes to compare installed/candidate.
    $policy = & $Docker run --rm --user 0 --memory 384m --memory-swap 384m --cpus 1 `
        --tmpfs /var/lib/apt/lists:rw,size=96m --entrypoint /bin/sh $image -ec `
        'apt-get update -qq; apt-cache policy openssl libssl3t64 libtiff6 libacl1 libsystemd0 zlib1g libncursesw6 libpcre2-8-0 liblzma5'
    $code = $LASTEXITCODE
    $results.Add(@{ service=$service; image=$image; exit_code=$code; utc=[DateTime]::UtcNow.ToString('o'); policy=($policy -join "`n") })
    $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath ".qa/audit2/stable-security-$stamp.json" -Encoding utf8
    if ($code -ne 0) { throw 'Security index check failed; do not infer that no updates exist' }
}
Write-Output "Stable/security installed-candidate evidence: .qa/audit2/stable-security-$stamp.json"
Write-Output 'This is package-index evidence, not a CVE scan or approval of unfixed findings.'
