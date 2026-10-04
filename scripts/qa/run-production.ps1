param(
    [ValidateSet('Prepare','Tests','Dependencies','Extract','Storage','Load','Scan','All')][string]$Stage = 'All',
    [ValidateSet('chemistryprodlocal','chemistryaudit2')][string]$Project = 'chemistryprodlocal',
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$folder = if ($Project -eq 'chemistryaudit2') { 'audit2' } else { 'production' }
$httpsPort = if ($Project -eq 'chemistryaudit2') { 18543 } else { 18443 }
$mailPort = if ($Project -eq 'chemistryaudit2') { 18525 } else { 18425 }
$compose = @('compose','--env-file',".qa/$folder/compose.env",'-p',$Project,'-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml')
$script:results = [System.Collections.Generic.List[object]]::new()
function Invoke-Gate([string]$Label, [string]$Executable, [string[]]$Arguments) {
    Write-Output "QA gate: $Label"
    & $Executable @Arguments
    $code = $LASTEXITCODE
    $script:results.Add(@{command=$Label; exit_code=$code; utc=[DateTime]::UtcNow.ToString('o')})
    $script:results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskRoot ".qa/$folder/commands-$Stage.json") -Encoding utf8
    if ($code -ne 0) { throw "Gate '$Label' failed with Exit Code $code. No publishing action performed." }
}
function Invoke-Compose([string]$Label, [string[]]$Arguments) {
    Invoke-Gate $Label $Docker ($compose + $Arguments)
}
if ($Stage -in @('Prepare','All')) {
    & (Join-Path $PSScriptRoot 'prepare-production.ps1') -Docker $Docker -Project $Project
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
        $env:QA_MEDIA_DIR = Join-Path $taskRoot ".qa/$folder/media"
        Invoke-Gate 'npm ci' 'npm.cmd' @('ci')
        Invoke-Gate 'install QA Chromium' 'npx.cmd' @('playwright','install','chromium')
        Invoke-Gate 'generate valid large WebM' 'node' @('scripts/generate-qa-video.mjs')
    } finally { Pop-Location }
    Invoke-Compose 'storage upload and access checkpoint' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.storage_drill','checkpoint')
}
if ($Stage -in @('Storage','All')) {
    # A subprocess gives the complete restore drill an explicit exit status,
    # including exceptions, and persists it alongside the other gate results.
    Invoke-Gate 'production persistence and new-store backup/restore' 'pwsh' @('-NoProfile','-File',
        (Join-Path $PSScriptRoot 'production-storage-drill.ps1'),'-Docker',$Docker,'-Project',$Project)
}
if ($Stage -in @('Tests','All')) {
    # Sequential suites avoid competing fault injection/auth windows. The
    # SQLite app's maintenance/reset uses QA_UNIT_REDIS_URL (DB15), never the
    # actual HTTPS app's Redis DB0. Reused live users wait for their real limits.
    Invoke-Compose 'API unit tests' @('run','--rm','--no-deps','-e','STORAGE_DIR=/tmp/qa-storage','qa-tests','python','-m','pytest','tests','--ignore=tests/integration','--tb=short','--junitxml=/qa/api-unit-tests.xml','-o','junit_logging=all')
    Invoke-Compose 'live integration tests' @('run','--rm','--no-deps','-e','STORAGE_DIR=/tmp/qa-storage','qa-tests','python','-m','pytest','tests/integration','--tb=short','--junitxml=/qa/api-integration-tests.xml','-o','junit_logging=all')
    $env:QA_BASE_URL = "https://localhost:$httpsPort"
    $env:QA_LOCAL_TLS = 'true'
    $env:QA_MAILPIT_URL = "http://127.0.0.1:$mailPort"
    $env:QA_REDIS_CONTAINER = "$Project-redis-1"
    $env:QA_DOCKER = $Docker
    $env:PLAYWRIGHT_JUNIT_OUTPUT_FILE = Join-Path $taskRoot ".qa/$folder/browser-tests.xml"
    $env:QA_PLAYWRIGHT_OUTPUT = Join-Path $taskRoot (".qa/$folder/browser-results-" + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
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
    Invoke-Compose '3 x 180s mixed browsing/video/upload load' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.qa_load')
}
if ($Stage -in @('Dependencies','All')) {
    Invoke-Compose 'clean editable/wheel install and exact runtime metadata' @('run','--rm','--no-deps','-v',"${taskRoot}/apps/api:/srv:ro",'-v',"${taskRoot}/scripts/qa/clean-python-install.sh:/tmp/clean-python-install.sh:ro",'qa-tests','sh','/tmp/clean-python-install.sh')
}
if ($Stage -in @('Scan','All')) {
    foreach ($target in @(@('api',"$Project-api"),@('web',"$Project-web"),@('s3','chrislusf/seaweedfs:4.48@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d'))) {
        Invoke-Gate "Docker Scout $($target[0])" $Docker @('scout','cves',$target[1],'--only-severity','critical,high','--format','sarif','--output',".qa/$folder/scout-$($target[0]).sarif")
    }
    # Scanner exit 0 means the scan completed, NOT that vulnerabilities are zero.
    Write-Output 'Review all SARIF findings. Successful scans do not authorize release.'
}
if ($Stage -in @('Extract','All')) {
    # Strict fidelity is a separate final gate. Structural detection/counts alone
    # do not prove the Arabic/scientific question text and ordered options match.
    Invoke-Compose 'blind Extract text and ordered-option fidelity' @('run','--rm','--no-deps','qa-tests','python','-m','scripts.qa_extract_fidelity','--output','/qa/extract-fidelity.json')
}
