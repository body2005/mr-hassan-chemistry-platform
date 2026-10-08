param(
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$snapshotRelative = ".qa/clean-gate-$stamp"
$snapshot = Join-Path $taskRoot $snapshotRelative
if (Test-Path -LiteralPath $snapshot) { throw 'Snapshot already exists; never overwrite it' }
$artifacts = Join-Path $taskRoot ".qa/audit2/clean-results-$stamp"
New-Item -ItemType Directory -Path $artifacts -Force | Out-Null
$results = [System.Collections.Generic.List[object]]::new()
function Run-Step([string]$label, [string]$executable, [string[]]$arguments) {
    & $executable @arguments
    $code = $LASTEXITCODE
    $results.Add(@{command=$label;exit_code=$code;utc=[DateTime]::UtcNow.ToString('o')})
    $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $artifacts 'commands.json') -Encoding utf8
    if ($code -ne 0) { throw "Clean gate '$label' failed ($code); retain artifacts and investigate" }
}
# Export the existing index only. Do NOT stage unknown files, copy .env,
# untracked runtime assets or rewrite history. Review the index first.
Run-Step 'export indexed sources' git @('checkout-index', "--prefix=$snapshotRelative/", '-a')
Run-Step 'clean secret scan (redacted, no exclusions)' $Docker @('run','--rm','-v',"${snapshot}:/repo:ro",'-v',"${artifacts}:/results",
    'zricethezav/gitleaks:v8.24.3@sha256:5d0147dc25c78f8cc2b9861ff8f5c9b4a41419ed60a9ce2217de5a215270b42b',
    'detect','--source','/repo','--no-git','--redact','--report-format','json','--report-path','/results/gitleaks.json','--exit-code=1')
$npm = if ($IsWindows) { 'npm.cmd' } else { 'npm' }
Push-Location (Join-Path $snapshot 'apps/web')
try {
    Run-Step 'clean npm ci' $npm @('ci')
    Run-Step 'clean lint' $npm @('run','lint')
    $env:VITE_API_URL = '/api/v1'
    Run-Step 'clean build' $npm @('run','build')
    # Catch auto-discovery differences caused by Git/ignored snapshot paths.
    # Build the working tree with VITE_API_URL=/api/v1 before this clean gate;
    # both exports must contain the same bytes, not just successfully compile.
    $workingDist = Join-Path $taskRoot 'apps/web/dist'
    $cleanDist = Join-Path $snapshot 'apps/web/dist'
    $different = [System.Collections.Generic.List[string]]::new()
    $workingFiles = @(Get-ChildItem -LiteralPath $workingDist -Recurse -File)
    $cleanFiles = @(Get-ChildItem -LiteralPath $cleanDist -Recurse -File)
    if ($workingFiles.Count -ne $cleanFiles.Count) { $different.Add('asset-count') }
    foreach ($file in $cleanFiles) {
        $relative = $file.FullName.Substring($cleanDist.Length + 1)
        $other = Join-Path $workingDist $relative
        if (!(Test-Path -LiteralPath $other) -or
            (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $other -Algorithm SHA256).Hash) {
            $different.Add($relative)
        }
    }
    $results.Add(@{command='clean/working web asset SHA-256 equivalence';
        exit_code=$(if ($different.Count) { 1 } else { 0 });
        compared_files=$cleanFiles.Count; mismatches=@($different);
        utc=[DateTime]::UtcNow.ToString('o')})
    $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $artifacts 'commands.json') -Encoding utf8
    if ($different.Count) { throw 'Clean web output differs; retain artifacts and fix source discovery/build inputs' }
    # Keep all suites isolated; limit concurrent jsdom workers on small hosts.
    Run-Step 'clean frontend unit tests' $npm @('test','--','--maxWorkers=1','--reporter=default','--reporter=junit',"--outputFile=$artifacts/frontend.xml")
} finally { Pop-Location }
Run-Step 'clean API image build (not deployed)' $Docker @('build','-f',"$snapshotRelative/infra/Dockerfile.api",'-t',"chemistryaudit2-clean-api:$stamp","$snapshotRelative/apps/api")
$env:VIDEO_UPLOAD_PUBLIC_ENDPOINT = 'https://localhost:18544'
$env:VIDEO_UPLOAD_PORT = '18544'
$env:VIDEO_UPLOAD_BIND = '127.0.0.1'
$compose = @('compose','--env-file','.qa/audit2/compose.env','-p','chemistryaudit2',
    '-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml','-f','infra/video-pipeline.override.yml')
# The synthetic snapshot (not the user's source checkout) is writable: this
# application creates uploads at startup. No original storage assets copied.
Run-Step 'clean API unit tests' $Docker ($compose + @('run','--rm','--no-deps','-v',"${snapshot}:/workspace",'-v',"${artifacts}:/clean-results",
    '-w','/workspace/apps/api','-e','PYTHONPATH=/workspace/apps/api','-e','STORAGE_DIR=/tmp/qa-clean-storage',
    'qa-tests','python','-m','pytest','tests','--ignore=tests/integration','-q','--tb=short','-o','cache_dir=/tmp/qa-clean-cache','--junitxml=/clean-results/backend.xml'))
