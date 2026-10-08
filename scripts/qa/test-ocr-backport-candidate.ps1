# Optional immutable compiled-cache repeat. Default clean reproduction remains
# prepare-ocr-backport.ps1 -Mode Build; this never adopts an app image.
param(
    [Parameter(Mandatory)][ValidatePattern('^sha256:[a-f0-9]{64}$')][string]$CompiledImage,
    [Parameter(Mandatory)][ValidatePattern('^/tmp/chemistry-ocr-backport\.[A-Za-z0-9]+/tesseract-5\.5\.0$')][string]$SourceDirectory,
    [Parameter(Mandatory)][string]$RuntimeDirectory,
    [string]$Docker='C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runtime=(Resolve-Path -LiteralPath $RuntimeDirectory).Path
$privateRoot=Join-Path $taskRoot '.qa'
$nativeAssets=Join-Path $taskRoot 'apps/api/scripts/native/tesseract'
if (!$runtime.StartsWith($privateRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or
    !(Test-Path -LiteralPath (Join-Path $runtime 'usr/bin/tesseract')) -or
    !(Test-Path -LiteralPath (Join-Path $runtime 'applied-patches.tsv'))) {
    throw 'Only a retained isolated QA candidate runtime is allowed'
}
$owner=& $Docker image inspect $CompiledImage --format '{{index .Config.Labels "chemistry.qa.candidate"}}'
if ($LASTEXITCODE -ne 0 -or $owner -ne 'true') { throw 'Not an immutable QA-only compiled candidate' }
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,6)
$artifacts=Join-Path $taskRoot ".qa/audit2/tesseract-native-tests-$stamp"
New-Item -ItemType Directory -Path (Join-Path $artifacts 'output') | Out-Null
$probe=@'
set -eu
test ! -e /candidate/usr
cp -a /runtime/usr /candidate/usr
for f in applied-patches.tsv signature.txt inttemp-stable-backport.patch inttemp-context-adaptations.diff stable-callsite.patch library-links.txt; do
  cp "/runtime/$f" "/candidate/$f"
done
sh /qa-tools/test-ocr-backports.sh "$1"
'@
$arguments=@('run','--rm','--network','none','--memory','768m','--memory-swap','768m',
    '--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges:true',
    '-e','QA_NATIVE_CANDIDATE=true','-v',"${runtime}:/runtime:ro",'-v',"${PSScriptRoot}:/qa-tools:ro",
    '-v',"${nativeAssets}:/native-backports:ro",'-v',"${artifacts}/output:/candidate",'--entrypoint','sh',$CompiledImage,'-c',$probe,'qa-native-test',$SourceDirectory)
& $Docker @arguments 2>&1 | Tee-Object -FilePath (Join-Path $artifacts 'native-tests.log')
$code=$LASTEXITCODE
@{image=$CompiledImage;source=$SourceDirectory;runtime=$runtime;arguments=$arguments;exit_code=$code;
    application_changed=$false;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $artifacts 'command.json') -Encoding utf8
Write-Output "Native-test output retained at $artifacts; no application adoption."
exit $code
