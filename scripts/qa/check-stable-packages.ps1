param(
    [Parameter(Mandatory)][ValidatePattern('^sha256:[a-f0-9]{64}$')][string]$Image,
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$artifacts = Join-Path $taskRoot ".qa/audit2/stable-packages-$stamp"
if (Test-Path -LiteralPath $artifacts) { throw 'Never overwrite a prior package assessment' }
New-Item -ItemType Directory -Path $artifacts | Out-Null
$probe = @'
set -eu
printf 'Configured Debian sources\n'
find /etc/apt/sources.list.d -type f -exec sed -n '1,80p' {} \;
apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=15 update
apt-cache policy openssl libssl3t64 libxml2 libstdc++6 libexpat1 libpcre2-8-0 xz-utils liblzma5 ffmpeg
printf 'Simulated stable upgrade (no installation)\n'
apt-get -s upgrade
'@
# No Compose environment, volumes, secrets, app network or Docker socket.
# Root/capabilities are limited to this disposable apt probe, never the API.
# SETUID/GID allow apt's unprivileged downloader; FOWNER avoids chmod warnings.
& $Docker run --rm --user 0:0 --memory 256m --cpus 0.5 --pids-limit 64 `
    --cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add CHOWN `
    --cap-add DAC_OVERRIDE --cap-add FOWNER --security-opt no-new-privileges `
    --entrypoint sh $Image -c $probe 2>&1 |
    Tee-Object -FilePath (Join-Path $artifacts 'policy.txt')
$code = $LASTEXITCODE
@{ command='disposable Debian source/candidate assessment and simulated upgrade';
    image=$Image; exit_code=$code; utc=[DateTime]::UtcNow.ToString('o');
    installed_packages_changed=$false } | ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $artifacts 'command.json') -Encoding utf8
if ($code -ne 0) { throw "Package assessment failed ($code); do not infer no fixes" }
