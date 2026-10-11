param([string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$scanner = 'aquasec/trivy:0.69.3@sha256:7228e304ae0f610a1fad937baa463598cadac0c2ac4027cc68f3a8b997115689'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$output = Join-Path $taskRoot ".qa/audit2/trivy-$stamp"
New-Item -ItemType Directory -Path $output | Out-Null
$results = @()
foreach ($service in @('api','video-worker')) {
    $target = "chemistryaudit2-$service-1"
    $owner = & $Docker inspect $target --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
    if ($LASTEXITCODE -ne 0 -or $owner -ne "chemistryaudit2/$service") { throw 'Unexpected runtime scan target' }
    $identity = & $Docker inspect $target --format '{{.Image}}'
    if ($LASTEXITCODE -ne 0 -or $identity -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Missing immutable runtime identity' }
    & $Docker run --rm --memory 768m --memory-swap 768m --cpus 1 `
        --cap-drop ALL --security-opt no-new-privileges `
        -v /var/run/docker.sock:/var/run/docker.sock -v "${output}:/results" `
        -v chemistryaudit2_trivy_cache:/root/.cache/trivy $scanner image --scanners vuln `
        --format sarif --output "/results/$service.sarif" --severity HIGH,CRITICAL --exit-code 1 $identity
    $code = $LASTEXITCODE
    $results += @{service=$service;image=$identity;scanner=$scanner;exit_code=$code;utc=[DateTime]::UtcNow.ToString('o')}
    $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $output 'commands.json') -Encoding utf8
}
if (@($results | Where-Object exit_code -ne 0).Count) { throw 'Image gate remains OPEN; inspect both SARIF files, no ignore/suppression applied' }
