param(
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe',
    [string]$SpecPattern = '',
    [string]$Grep = '',
    [switch]$Build
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$taskOutput = Join-Path $taskRoot ".qa/audit2/trusted-browser-$stamp"
New-Item -ItemType Directory -Path $taskOutput | Out-Null
$image = 'chemistryaudit2-browser-qa'
$Specs = @($SpecPattern.Split(',', [StringSplitOptions]::RemoveEmptyEntries))
if ($Build) {
    & $Docker build -t $image -f infra/Dockerfile.browser-qa apps/web
    if ($LASTEXITCODE -ne 0) { throw 'Trusted QA browser build failed' }
}
$imageId = & $Docker image inspect $image --format '{{.Id}}'
if ($LASTEXITCODE -ne 0 -or $imageId -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Build the trusted QA runner first' }
$runtimeImages = [ordered]@{}
foreach ($service in @('api','web','proxy','redis')) {
    $owner = & $Docker inspect "chemistryaudit2-$service-1" --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
    if ($LASTEXITCODE -ne 0 -or $owner -ne "chemistryaudit2/$service") { throw 'Unexpected QA target' }
    $runtimeImages[$service] = & $Docker inspect "chemistryaudit2-$service-1" --format '{{.Image}}'
    if ($LASTEXITCODE -ne 0 -or $runtimeImages[$service] -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Missing actual runtime image identity' }
}
$taskHead = & git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Cannot identify the checkout' }
$taskCertHash = (Get-FileHash -LiteralPath '.qa/audit2/secrets/cert.pem' -Algorithm SHA256).Hash
$taskMedia = (Resolve-Path '.qa/audit2/media').Path
$taskCert = (Resolve-Path '.qa/audit2/secrets/cert.pem').Path
$arguments = @('run','--rm','--init','--name',"chemistryaudit2-browser-$stamp",
    '--memory','1536m','--memory-swap','1536m','--cpus','1.5','--shm-size','512m',
    '--group-add','0','--add-host','host.docker.internal:host-gateway',
    '-v','/var/run/docker.sock:/var/run/docker.sock',
    '-v',"${taskCert}:/qa-ca/cert.pem:ro",'-v',"${taskMedia}:/qa-media:ro",'-v',"${taskOutput}:/qa-results",
    '-v',"${taskRoot}/apps/api/tests/fixtures:/api/tests/fixtures:ro",
    '-e','QA_PROJECT=chemistryaudit2','-e','QA_BASE_URL=https://localhost:18543','-e','QA_CA_CERT=/qa-ca/cert.pem',
    '-e','QA_LOCAL_TLS=false','-e','QA_DOCKER=/usr/bin/docker','-e','QA_REDIS_CONTAINER=chemistryaudit2-redis-1',
    '-e','QA_MAILPIT_URL=http://host.docker.internal:18525','-e','QA_MEDIA_DIR=/qa-media','-e','QA_VIDEO_FILE=/qa-media/video.webm',
    '-e','QA_PLAYWRIGHT_OUTPUT=/qa-results/artifacts','-e','PLAYWRIGHT_JUNIT_OUTPUT_FILE=/qa-results/browser.xml',
    $imageId,'npx','playwright','test','--config','playwright.qa.config.ts','--reporter=list,junit') + $Specs
if ($Grep) { $arguments += @('--grep', $Grep) }
& $Docker @arguments
$code = $LASTEXITCODE
foreach ($service in $runtimeImages.Keys) {
    $afterImage = & $Docker inspect "chemistryaudit2-$service-1" --format '{{.Image}}'
    if ($LASTEXITCODE -ne 0 -or $afterImage -ne $runtimeImages[$service]) { $code = 1 }
}
@{command='trusted isolated browser (TLS validation enabled)';runner_image=$imageId;runtime_images=$runtimeImages;git_head=$taskHead;source_state='local working tree, not necessarily committed';public_certificate_pem_sha256=$taskCertHash;exit_code=$code;utc=[DateTime]::UtcNow.ToString('o');specs=$Specs;grep=$Grep} |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $taskOutput 'command.json') -Encoding utf8
if ($code -ne 0) { throw "Browser gate failed (Exit Code $code); inspect the raw result" }
