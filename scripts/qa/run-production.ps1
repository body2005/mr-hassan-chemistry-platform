param(
    [ValidateSet('Prepare','Tests','Storage','Load','Scan','All')][string]$Stage = 'All',
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$compose = @('compose','--env-file','.qa/production/compose.env','-p','chemistryprodlocal','-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml')
$script:results = [System.Collections.Generic.List[object]]::new()
function Invoke-Gate([string]$Label, [string]$Executable, [string[]]$Arguments) {
    Write-Output "QA gate: $Label"
    & $Executable @Arguments
    $code = $LASTEXITCODE
    $script:results.Add(@{command=$Label; exit_code=$code; utc=[DateTime]::UtcNow.ToString('o')})
    $script:results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskRoot ".qa/production/commands-$Stage.json") -Encoding utf8
    if ($code -ne 0) { throw "Gate '$Label' failed with Exit Code $code. No publishing action performed." }
}
function Invoke-Compose([string]$Label, [string[]]$Arguments) {
    Invoke-Gate $Label $Docker ($compose + $Arguments)
}
if ($Stage -in @('Prepare','All')) {
    & (Join-Path $PSScriptRoot 'prepare-production.ps1') -Docker $Docker
    Invoke-Compose 'config -q' @('config','-q')
    # Sequential builds guarantee the QA runner extends the freshly built API.
    Invoke-Compose 'build production images' @('build','api','worker','migration','s3-init','web')
    Invoke-Compose 'build QA runner' @('build','qa-tests')
    Invoke-Compose 'start production template locally' @('up','-d','--wait','--wait-timeout','160')
    Invoke-Compose 'reload bind-mounted proxy config' @('exec','-T','proxy','nginx','-s','reload')
    Invoke-Compose 'seed synthetic identities' @('exec','-T','-e','QA_ISOLATED=true','api','sh','/srv/entrypoint-prod.sh','python','scripts/seed_qa.py')
    Invoke-Compose 'generate valid large PDF' @('run','--rm','--no-deps','qa-tests','python','scripts/generate_qa_pdf.py')
    Push-Location (Join-Path $taskRoot 'apps/web')
    try {
        Invoke-Gate 'npm ci' 'npm.cmd' @('ci')
        Invoke-Gate 'install QA Chromium' 'npx.cmd' @('playwright','install','chromium')
        Invoke-Gate 'generate valid large WebM' 'node' @('scripts/generate-qa-video.mjs')
    } finally { Pop-Location }
    Invoke-Compose 'storage upload and access checkpoint' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.storage_drill','checkpoint')
}
if ($Stage -in @('Storage','All')) {
    & (Join-Path $PSScriptRoot 'production-storage-drill.ps1') -Docker $Docker
}
if ($Stage -in @('Tests','All')) {
    # Do NOT run API and browser suites concurrently: they isolate counters in
    # this disposable Redis between cases, while real limits stay on in cases.
    Invoke-Compose 'full API tests including integration' @('run','--rm','--no-deps','qa-tests','python','-m','pytest','tests','--tb=short','--junitxml=/qa/api-tests.xml')
    $env:QA_BASE_URL = 'https://localhost:18443'
    $env:QA_LOCAL_TLS = 'true'
    $env:QA_MAILPIT_URL = 'http://127.0.0.1:18425'
    $env:QA_REDIS_CONTAINER = 'chemistryprodlocal-redis-1'
    $env:QA_DOCKER = $Docker
    $env:PLAYWRIGHT_JUNIT_OUTPUT_FILE = Join-Path $taskRoot '.qa/production/browser-tests.xml'
    Push-Location (Join-Path $taskRoot 'apps/web')
    try {
        Invoke-Gate 'npm run lint' 'npm.cmd' @('run','lint')
        Invoke-Gate 'npm run build' 'npm.cmd' @('run','build')
        Invoke-Gate 'frontend unit tests' 'npm.cmd' @('run','test','--','--run')
        Invoke-Gate 'Playwright production HTTPS' 'npx.cmd' @('playwright','test','--config','playwright.qa.config.ts','--reporter=list,junit')
        Invoke-Gate 'npm audit' 'npm.cmd' @('audit','--audit-level=high')
    } finally { Pop-Location }
    Invoke-Gate 'git diff --check' 'git' @('diff','--check')
}
if ($Stage -in @('Load','All')) {
    Invoke-Compose '3 x 60s mixed browsing/video/upload load' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.qa_load')
}
if ($Stage -in @('Scan','All')) {
    foreach ($target in @(@('api','chemistryprodlocal-api'),@('web','chemistryprodlocal-web'),@('s3','chrislusf/seaweedfs:4.48@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d'))) {
        Invoke-Gate "Docker Scout $($target[0])" $Docker @('scout','cves',$target[1],'--only-severity','critical,high','--format','sarif','--output',".qa/production/scout-$($target[0]).sarif")
    }
    # Scanner exit 0 means the scan completed, NOT that vulnerabilities are zero.
    Write-Output 'Review all SARIF findings. Successful scans do not authorize release.'
}
