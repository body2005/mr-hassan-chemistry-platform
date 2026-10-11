param([string]$Docker='C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe',
      [ValidateSet('chemistryaudit2','chemistryprodlocal')][string]$Project='chemistryaudit2')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$artifacts=Join-Path $taskRoot ".qa/audit2/zlib-source-review-$stamp"
New-Item -ItemType Directory -Path $artifacts | Out-Null
$runtime=@()
foreach($service in @('api','video-worker')){
    $target="$Project-$service-1"
    $owner=& $Docker inspect $target --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}'
    if($LASTEXITCODE -ne 0 -or $owner -ne "$Project/$service"){throw 'Unexpected zlib review runtime target'}
    $identity=& $Docker inspect $target --format '{{.Image}}'
    if($LASTEXITCODE -ne 0 -or $identity -notmatch '^sha256:[a-f0-9]{64}$'){throw 'Missing immutable runtime image'}
    $metadata=& $Docker exec $target dpkg-query -W '-f=${binary:Package}|${Version}|${source:Package}|${source:Version}\n' zlib1g
    if($LASTEXITCODE -ne 0 -or $metadata -ne 'zlib1g:amd64|1:1.3.dfsg+really1.3.1-1+b1|zlib|1:1.3.dfsg+really1.3.1-1'){
        throw 'Installed zlib source differs from the pinned review. Re-audit the actual package; do not apply this conclusion.'
    }
    $runtime+=@{service=$service;image=$identity;package_source_metadata=$metadata}
}
$runtime | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $artifacts 'runtime.json') -Encoding utf8
$sourceReview=@'
set -eu
cd /tmp
apt-get update
apt-get install -y --no-install-recommends curl ca-certificates gpgv debian-keyring xz-utils patch
task_base=https://deb.debian.org/debian/pool/main/z/zlib
curl --fail --location --proto '=https' --tlsv1.2 --retry 2 -o zlib.dsc "$task_base/zlib_1.3.dfsg+really1.3.1-1.dsc"
printf '%s  zlib.dsc\n' 'ede2791e29c1d3b422f9208bdd7edf040c20445ea1e7453a72037576e64fa197' | sha256sum -c -
gpgv --status-fd 1 --keyring /usr/share/keyrings/debian-keyring.gpg zlib.dsc > /qa/signature.txt
grep -E '^\[GNUPG:\] VALIDSIG ADE668AA675718B59FE29FEA24D68B725D5487D0 .* 3F2568AAC26998F9E813A1C5C3F436CA30F5D8EB$' /qa/signature.txt
curl --fail --location --proto '=https' --tlsv1.2 --retry 2 -o source.tar.gz "$task_base/zlib_1.3.dfsg+really1.3.1.orig.tar.gz"
curl --fail --location --proto '=https' --tlsv1.2 --retry 2 -o debian.tar.xz "$task_base/zlib_1.3.dfsg+really1.3.1-1.debian.tar.xz"
printf '%s  source.tar.gz\n' '60dd315c07f616887caa029408308a018ace66e3d142726a97db164b3b8f69fb' | sha256sum -c -
printf '%s  debian.tar.xz\n' '9ed525955ce9fb0c1b39be8ff98f73450dbfc6305a9a27e6149c8972d38a0a9e' | sha256sum -c -
mkdir source
tar -xf source.tar.gz -C source --strip-components=1
tar -xf debian.tar.xz -C source
cd source
printf 'Debian quilt series\n'
if test -f debian/patches/series; then
  cat debian/patches/series
  while read -r task_patch task_flags; do
    case "$task_patch" in ''|'#'*) continue ;; esac
    patch --fuzz=0 -p1 < "debian/patches/$task_patch"
  done < debian/patches/series
fi
printf 'Actual reviewed source symbols and provenance\n'
grep '^#define ZLIB_VERSION' zlib.h
sha256sum gzwrite.c
cp gzwrite.c /qa/gzwrite.c
cp /tmp/zlib.dsc /qa/zlib.dsc
if grep -n 'gz_vacate' gzwrite.c; then
  echo 'Affected helper exists; full patch/path analysis still required.'
else
  echo 'gz_vacate absent from authenticated Debian1.3.1 source plus quilt patches.'
fi
printf 'Installed actual source metadata must separately match this reviewed package. No scanner suppression.\n'
'@
& $Docker run --rm --user 0:0 --memory 256m --cpus 0.5 --pids-limit 64 `
    --cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add CHOWN `
    --cap-add DAC_OVERRIDE --cap-add FOWNER --security-opt no-new-privileges:true `
    --mount "type=bind,source=$artifacts,target=/qa" --entrypoint sh `
    'python:3.12.15-slim-trixie@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016' `
    -c $sourceReview 2>&1 | Tee-Object -FilePath (Join-Path $artifacts 'source-review.log') | Select-Object -Last 22
$code=$LASTEXITCODE
@{command='authenticated Debian zlib source/quilt review; no runtime modifications';
  exit_code=$code;utc=[DateTime]::UtcNow.ToString('o');artifacts=$artifacts} |
  ConvertTo-Json | Set-Content -LiteralPath (Join-Path $artifacts 'command.json') -Encoding utf8
exit $code
