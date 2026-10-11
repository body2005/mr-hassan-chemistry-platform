# Reproducible isolated native-security candidate. No application replacement.
param(
    [ValidateSet('Prepare','Build')][string]$Mode='Prepare',
    [ValidatePattern('^sha256:[a-f0-9]{64}$')][string]$ToolsImage,
    [string]$Docker='C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,6)
$taskDir=Join-Path $taskRoot ".qa/audit2/tesseract-backport-$stamp"
if(Test-Path -LiteralPath $taskDir){throw 'Never overwrite a candidate or prior failure'}
foreach($folder in @('inputs','patches','output')){
    New-Item -ItemType Directory -Path (Join-Path $taskDir $folder) | Out-Null
}
$records=[System.Collections.Generic.List[object]]::new()
function Get-PinnedInput([string]$Url,[string]$Destination,[string]$Expected){
    if(Test-Path -LiteralPath $Destination){throw 'Never overwrite an input'}
    Invoke-WebRequest -Uri $Url -OutFile $Destination -TimeoutSec 60
    $actual=(Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
    $record=@{url=$Url;sha256=$actual;expected_sha256=$Expected;
        exit_code=$(if($actual -ceq $Expected){0}else{1});utc=[DateTime]::UtcNow.ToString('o')}
    $records.Add($record)
    $records | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $taskDir 'downloads.json') -Encoding utf8
    if($actual -cne $Expected){throw 'Upstream bytes changed; review rather than changing the pinned hash automatically'}
}
foreach($source in @(
    @('tesseract_5.5.0-1.dsc','80dc6a0e5d6189b3fe9df632a114642b17ed8582a43b55e45ca508efb995cf1c'),
    @('tesseract_5.5.0.orig.tar.gz','f2fb34ca035b6d087a42875a35a7a5c4155fa9979c6132365b1e5a28ebc3fc11'),
    @('tesseract_5.5.0-1.debian.tar.xz','339c1e99003ed57552296f0ce758650b8c62d5f1222bb22c6c93a519dc90d20d')
)){
    Get-PinnedInput "https://deb.debian.org/debian/pool/main/t/tesseract/$($source[0])" (Join-Path $taskDir "inputs/$($source[0])") $source[1]
}
$nativeAssets=Join-Path $taskRoot 'apps/api/scripts/native/tesseract'
foreach($line in (Get-Content (Join-Path $nativeAssets 'backports.tsv'))){
    if(!$line -or $line.StartsWith('#')){continue}
    $fields=$line.Split(' ')
    if($fields.Count -ne 3 -or $fields[1] -notmatch '^[a-f0-9]{40}$' -or $fields[2] -notmatch '^[a-f0-9]{64}$'){
        throw 'Invalid reviewed patch manifest'
    }
    Get-PinnedInput "https://github.com/tesseract-ocr/tesseract/commit/$($fields[1]).patch" (Join-Path $taskDir "patches/$($fields[1]).patch") $fields[2]
}
$baseImage=if($ToolsImage){$ToolsImage}else{'python:3.12.15-slim-trixie@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016'}
# Default bridge, not the application network; no Docker socket, compose env,
# identity/data volumes or secrets. Full Build must not overlap live heavy QA.
$arguments=@('run','--name',"chemistryaudit2-ocr-backport-$stamp",
    '--label','com.docker.compose.project=chemistryaudit2',
    '--label','com.docker.compose.service=ocr-backport-candidate',
    '--label','chemistry.qa.candidate=true','--memory','768m','--memory-swap','768m',
    '--cpus','1','--pids-limit','128','--cap-drop','ALL',
    '--cap-add','CHOWN','--cap-add','SETUID','--cap-add','SETGID',
    '--cap-add','DAC_OVERRIDE','--cap-add','FOWNER',
    '--security-opt','no-new-privileges:true','-e','QA_NATIVE_CANDIDATE=true',
    '-e',"QA_BACKPORT_PREPARE_ONLY=$(if($Mode -eq 'Prepare'){'true'}else{'false'})",
    '-v',"${taskDir}/inputs:/inputs:ro",'-v',"${taskDir}/patches:/patches:ro",
    '-v',"${PSScriptRoot}:/qa-tools:ro",'-v',"${nativeAssets}:/native-backports:ro",
    '-v',"${taskDir}/output:/candidate",
    '--entrypoint','sh',$baseImage,'/qa-tools/build-ocr-backport-candidate.sh')
& $Docker @arguments 2>&1 | Tee-Object -FilePath (Join-Path $taskDir 'candidate.log')
$code=$LASTEXITCODE
@{mode=$Mode;image=$baseImage;exit_code=$code;utc=[DateTime]::UtcNow.ToString('o');
    artifacts=$taskDir;application_changed=$false;arguments=$arguments} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskDir 'command.json') -Encoding utf8
Write-Output "Candidate artifacts retained at $taskDir; no application adoption."
exit $code
