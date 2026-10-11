# Run the unchanged strict comparator against an immutable baseline and a
# separately built native candidate. No app network, secrets or data volumes.
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^sha256:[a-f0-9]{64}$')][string]$Image,
    [Parameter(Mandatory=$true)][string]$CandidateDirectory,
    [string]$Docker = 'C:/Users/body/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$candidate = (Resolve-Path -LiteralPath $CandidateDirectory).Path
if (!(Test-Path -LiteralPath (Join-Path $candidate 'usr/bin/tesseract')) -or
    !(Test-Path -LiteralPath (Join-Path $candidate 'provenance.txt'))) {
    throw 'Candidate binary/provenance is missing; build the isolated candidate first'
}
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$results = Join-Path $repo ".qa/audit2/ocr-runtime-$stamp"
New-Item -ItemType Directory -Path $results | Out-Null
$fixtures = Join-Path $repo 'apps/api/tests/fixtures/blind_inputs'
$commands = @()
foreach ($kind in @('baseline','candidate')) {
    $arguments = @('run','--rm','--network','none','--read-only',
        '--user','10001:10001','--memory','768m','--cpus','1','--pids-limit','128',
        '--cap-drop','ALL','--security-opt','no-new-privileges:true',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=256m,uid=10001,gid=10001',
        '--tmpfs','/srv/storage:rw,noexec,nosuid,size=64m,uid=10001,gid=10001',
        '-e','APP_ENV=test','-e','STORAGE_DIR=/tmp/uploads',
        '-v',"${fixtures}:/srv/tests/fixtures/blind_inputs:ro",'-v',"${results}:/qa")
    if ($kind -eq 'candidate') {
        $arguments += @('-v',"${candidate}:/candidate:ro",
            '-v',"${candidate}/usr/bin/tesseract:/usr/bin/tesseract:ro",
            '-e','LD_LIBRARY_PATH=/candidate/usr/lib/x86_64-linux-gnu',
            '-e','TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata')
    }
    $arguments += @($Image,'python','-m','scripts.qa_extract_fidelity',
        '--output',"/qa/$kind.json")
    $started = [DateTime]::UtcNow.ToString('o')
    & $Docker @arguments 2>&1 | Tee-Object -FilePath (Join-Path $results "$kind.log")
    $code = $LASTEXITCODE
    $commands += @{kind=$kind;image=$Image;started=$started;completed=[DateTime]::UtcNow.ToString('o');exitCode=$code;arguments=$arguments}
    $commands | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $results 'commands.json') -Encoding utf8
    if ($code -notin @(0,1) -or !(Test-Path -LiteralPath (Join-Path $results "$kind.json"))) {
        throw "$kind did not produce a strict result (Exit$code); not a fidelity failure count"
    }
}
$baseline = Get-Content -Raw -LiteralPath (Join-Path $results 'baseline.json') | ConvertFrom-Json
$replacement = Get-Content -Raw -LiteralPath (Join-Path $results 'candidate.json') | ConvertFrom-Json
if ($baseline.parser_ocr_version -ne $replacement.parser_ocr_version -or
    $baseline.results.Count -ne $replacement.results.Count) { throw 'Different comparator/parser scope' }
$comparisons = @()
for ($i = 0; $i -lt $baseline.results.Count; $i++) {
    $before = $baseline.results[$i]
    $after = $replacement.results[$i]
    if ($before.filename -ne $after.filename -or $before.sha256 -ne $after.sha256) {
        throw 'Source fixtures differ; no comparison accepted'
    }
    $comparisons += @{filename=$before.filename;sha256=$before.sha256;
        baselineCount=$before.actual_count;candidateCount=$after.actual_count;
        baselineMatching=$before.fully_matching_questions;candidateMatching=$after.fully_matching_questions;
        baselineCER=$before.character_error_rate;candidateCER=$after.character_error_rate;
        identicalParsedOutput=(($before.actual | ConvertTo-Json -Depth 30 -Compress) -ceq ($after.actual | ConvertTo-Json -Depth 30 -Compress))}
}
@{image=$Image;parser=$baseline.parser_ocr_version;baseline=@{passed=$baseline.passed;failed=$baseline.failed;skipped=$baseline.skipped};
    candidate=@{passed=$replacement.passed;failed=$replacement.failed;skipped=$replacement.skipped};files=$comparisons} |
    ConvertTo-Json -Depth 8 | Tee-Object -FilePath (Join-Path $results 'comparison.json')
# Equivalent/dependency-reduced does NOT mean strict OCR is fixed.
if ($baseline.failed -or $replacement.failed) { exit 1 }
