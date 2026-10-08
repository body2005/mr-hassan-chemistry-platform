# Dependency-change parity only. This does not repair or waive OCR accuracy.
param(
    [Parameter(Mandatory)][ValidatePattern('^sha256:[a-f0-9]{64}$')][string]$BaselineImage,
    [Parameter(Mandatory)][ValidatePattern('^sha256:[a-f0-9]{64}$')][string]$CandidateImage,
    [string]$Docker='C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$fixtures=Join-Path $taskRoot 'apps/api/tests/fixtures/blind_inputs'
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$output=Join-Path $taskRoot ".qa/audit2/extract-image-parity-$stamp"
New-Item -ItemType Directory -Path $output | Out-Null
$probe=@'
import hashlib,json,pathlib,pyexpat,subprocess
root=pathlib.Path('/srv')
files=['app/services/document_parsers.py','app/services/exam_text_extractor.py','scripts/qa_extract_fidelity.py']
source={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
models={name:hashlib.sha256(pathlib.Path('/usr/share/tesseract-ocr/5/tessdata',name+'.traineddata').read_bytes()).hexdigest() for name in ['ara','eng','osd']}
ocr=subprocess.check_output(['dpkg-query','-W','-f=${Version}','tesseract-ocr']).decode().strip()
print(json.dumps({'source':source,'models':models,'tesseract_package_version':ocr,'python_expat':pyexpat.EXPAT_VERSION}))
'@
$inventory=@{}
$images=@{baseline=$BaselineImage;candidate=$CandidateImage}
$commands=@()
foreach($kind in @('baseline','candidate')){
    $image=$images[$kind]
    & $Docker image inspect $image --format '{{.Id}}' | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Immutable comparison image missing; do not substitute a tag'}
    $argsList=@('run','--rm','--network','none','--read-only','--entrypoint','python',
        '--user','10001:10001','--memory','768m','--memory-swap','768m',
        '--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges:true',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=256m,uid=10001,gid=10001',
        '--tmpfs','/srv/storage:rw,noexec,nosuid,size=64m,uid=10001,gid=10001',
        '-e','APP_ENV=test','-e','STORAGE_DIR=/tmp/uploads')
    $raw=& $Docker @argsList $image -c $probe
    $code=$LASTEXITCODE
    if($code -ne 0){throw "Could not read $kind source/model inventory: Exit$code"}
    $inventory[$kind]=$raw | ConvertFrom-Json -AsHashtable
    $inventory[$kind] | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $output "$kind-inventory.json") -Encoding utf8
}
foreach($category in @('source','models')){
    foreach($name in $inventory.baseline[$category].Keys){
        if($inventory.baseline[$category][$name] -ne $inventory.candidate[$category][$name]){
            throw "Comparison scope differs ($category/$name); dependency parity cannot be claimed"
        }
    }
}
if($inventory.baseline.tesseract_package_version -ne $inventory.candidate.tesseract_package_version){
    throw 'OCR package version differs; this comparison cannot attribute changes solely to the dependency update'
}
foreach($kind in @('baseline','candidate')){
    $image=$images[$kind]
    $argsList=@('run','--rm','--network','none','--read-only','--entrypoint','python',
        '--user','10001:10001','--memory','768m','--memory-swap','768m',
        '--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges:true',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=256m,uid=10001,gid=10001',
        '--tmpfs','/srv/storage:rw,noexec,nosuid,size=64m,uid=10001,gid=10001',
        '-e','APP_ENV=test','-e','STORAGE_DIR=/tmp/uploads',
        '-v',"${fixtures}:/srv/tests/fixtures/blind_inputs:ro",'-v',"${output}:/qa",$image,
        '-m','scripts.qa_extract_fidelity','--output',"/qa/$kind.json")
    & $Docker @argsList 2>&1 | Tee-Object -FilePath (Join-Path $output "$kind.log")
    $code=$LASTEXITCODE
    $commands+=@{kind=$kind;image=$image;exit_code=$code;utc=[DateTime]::UtcNow.ToString('o')}
    $commands | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $output 'commands.json') -Encoding utf8
    if($code -notin @(0,1) -or !(Test-Path -LiteralPath (Join-Path $output "$kind.json"))){
        throw "$kind produced no complete strict result; this is not a counted OCR failure"
    }
}
$baseline=Get-Content -Raw -LiteralPath (Join-Path $output 'baseline.json') | ConvertFrom-Json
$candidate=Get-Content -Raw -LiteralPath (Join-Path $output 'candidate.json') | ConvertFrom-Json
if($baseline.parser_ocr_version -ne $candidate.parser_ocr_version -or $baseline.results.Count -ne $candidate.results.Count){
    throw 'Different strict comparator/parser scope'
}
$comparison=@()
for($i=0;$i -lt $baseline.results.Count;$i++){
    $before=$baseline.results[$i]; $after=$candidate.results[$i]
    if($before.filename -ne $after.filename -or $before.sha256 -ne $after.sha256){throw 'Comparison fixtures differ'}
    $comparison+=@{filename=$before.filename;sha256=$before.sha256;
        baselineMatching=$before.fully_matching_questions;candidateMatching=$after.fully_matching_questions;
        baselineCER=$before.character_error_rate;candidateCER=$after.character_error_rate;
        identicalParsedOutput=(($before.actual | ConvertTo-Json -Depth 30 -Compress) -ceq ($after.actual | ConvertTo-Json -Depth 30 -Compress));
        identicalRawPages=(($before.raw_pages | ConvertTo-Json -Depth 10 -Compress) -ceq ($after.raw_pages | ConvertTo-Json -Depth 10 -Compress))}
}
$parity=@($comparison | Where-Object { !$_.identicalParsedOutput -or !$_.identicalRawPages }).Count -eq 0
@{baseline_image=$BaselineImage;candidate_image=$CandidateImage;parser=$baseline.parser_ocr_version;
    baseline=@{passed=$baseline.passed;failed=$baseline.failed;skipped=$baseline.skipped};
    candidate=@{passed=$candidate.passed;failed=$candidate.failed;skipped=$candidate.skipped};
    dependency_output_parity=$parity;files=$comparison} | ConvertTo-Json -Depth 8 |
    Tee-Object -FilePath (Join-Path $output 'comparison.json')
if(!$parity){exit 2}
# Retain the known deferred Biology failure as a failure, not a silent skip.
if($baseline.failed -or $candidate.failed){exit 1}
exit 0
