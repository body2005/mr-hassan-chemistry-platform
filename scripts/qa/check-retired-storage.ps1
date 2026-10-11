param([string]$Docker='C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $taskRoot
# No application secrets, network, Docker socket or storage volumes are mounted.
$image='python:3.12.15-slim-trixie@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016'
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$log=Join-Path $taskRoot ".qa/audit2/retired-storage-$stamp.log"
& $Docker run --rm --network none --read-only --user 10001:10001 --cpus 0.5 --memory 128m --memory-swap 128m --pids-limit 64 --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp:rw,nosuid,nodev,noexec,size=16m,uid=10001,gid=10001 -v "${taskRoot}/infra/scripts:/legacy:ro" -v "${taskRoot}/scripts/qa/tests:/qa-tools:ro" $image python -B /qa-tools/test_retired_storage_scripts.py 2>&1 | Tee-Object -FilePath $log
$code=$LASTEXITCODE
@{command='offline retired backup/restore guards';exit_code=$code;log=$log;utc=[DateTime]::UtcNow.ToString('o')} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRoot ".qa/audit2/retired-storage-$stamp.json") -Encoding utf8
exit $code
