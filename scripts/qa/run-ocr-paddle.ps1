param(
    [string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe',
    [ValidateSet('lines','words')][string]$Mode='lines'
)
$ErrorActionPreference = 'Stop'
$qaRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $qaRoot
# QA experiment only: no compose.env, secrets, DB network or Docker socket.
# Run after fault/load/restore, never during their measurements.
$qaCandidateRoot = Join-Path $qaRoot '.qa/audit2/paddle-candidate'
New-Item -ItemType Directory -Force -Path $qaCandidateRoot | Out-Null
& $Docker build -f infra/qa/Dockerfile.ocr-candidate -t chemistryaudit2-ocr-candidate infra/qa
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Docker run --rm --entrypoint python --cpus=1 --memory=2g --pids-limit=128 `
    -e APP_ENV=development -e REDIS_REQUIRED=false -e PYTHONPATH=/srv `
    -e PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true `
    -v "${qaCandidateRoot}:/qa-paddle" `
    -v "${qaRoot}/apps/api/scripts/qa_ocr_paddle.py:/srv/scripts/qa_ocr_paddle.py:ro" `
    -v "${qaRoot}/apps/api/scripts/qa_ocr_paddle_setup.py:/srv/scripts/qa_ocr_paddle_setup.py:ro" `
    -v "${qaRoot}/apps/api/scripts/qa_extract_fidelity.py:/srv/scripts/qa_extract_fidelity.py:ro" `
    -v "${qaRoot}/apps/api/tests/fixtures/blind_inputs:/srv/tests/fixtures/blind_inputs:ro" `
    chemistryaudit2-ocr-candidate -m scripts.qa_ocr_paddle_setup
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
# Actual image recognition has NO network, including model-source checks.
& $Docker run --rm --network none --entrypoint /qa-paddle/venv/bin/python `
    --cpus=1 --memory=2g --pids-limit=128 `
    -e APP_ENV=development -e REDIS_REQUIRED=false -e PYTHONPATH=/srv `
    -e PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true `
    -v "${qaCandidateRoot}:/qa-paddle" `
    -v "${qaRoot}/apps/api/scripts/qa_ocr_paddle.py:/srv/scripts/qa_ocr_paddle.py:ro" `
    -v "${qaRoot}/apps/api/scripts/qa_extract_fidelity.py:/srv/scripts/qa_extract_fidelity.py:ro" `
    -v "${qaRoot}/apps/api/tests/fixtures/blind_inputs:/srv/tests/fixtures/blind_inputs:ro" `
    chemistryaudit2-ocr-candidate -m scripts.qa_ocr_paddle `
    --model-dir /qa-paddle/arabic_PP-OCRv5_mobile_rec_infer --mode $Mode --output "/qa-paddle/result-$Mode.json"
exit $LASTEXITCODE
