param([string]$Docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskQa = Join-Path $taskRoot '.qa/production'
$taskSecrets = Join-Path $taskQa 'secrets'
New-Item -ItemType Directory -Force -Path $taskSecrets, (Join-Path $taskQa 'backups'), (Join-Path $taskQa 'media') | Out-Null
foreach ($name in @('postgres_password','app_secret_key','s3_password','smtp_password')) {
    $path = Join-Path $taskSecrets $name
    if (!(Test-Path -LiteralPath $path)) {
        $bytes = New-Object byte[] 48
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        [IO.File]::WriteAllText($path, [Convert]::ToBase64String($bytes))
    }
}
if (!(Test-Path (Join-Path $taskSecrets 'cert.pem'))) {
    & $Docker run --rm -v "${taskSecrets}:/certs" --entrypoint openssl 'python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f' req -x509 -newkey rsa:3072 -nodes -days 14 -keyout /certs/key.pem -out /certs/cert.pem -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,DNS:mailpit,DNS:proxy,IP:127.0.0.1' -addext 'basicConstraints=critical,CA:TRUE'
    if ($LASTEXITCODE -ne 0) { throw 'Local certificate generation failed' }
}
$unix = $taskQa.Replace('\','/')
$contents = @"
PUBLIC_ORIGIN=https://localhost:18443
PUBLIC_HTTP_BIND=127.0.0.1
PUBLIC_HTTPS_BIND=127.0.0.1
PUBLIC_HTTP_PORT=18480
PUBLIC_HTTPS_PORT=18443
S3_ACCESS_KEY=production-qa-storage
S3_BUCKET=chemistry-production-qa
POSTGRES_USER=lms
POSTGRES_DB=lms
PRIVATE_SUBNET=172.30.121.0/24
BACKUP_DIR=$unix/backups
QA_ARTIFACT_DIR=$unix
POSTGRES_PASSWORD_FILE=$unix/secrets/postgres_password
APP_SECRET_KEY_FILE=$unix/secrets/app_secret_key
S3_PASSWORD_FILE=$unix/secrets/s3_password
SMTP_PASSWORD_FILE=$unix/secrets/smtp_password
TLS_CERT_FILE=$unix/secrets/cert.pem
TLS_KEY_FILE=$unix/secrets/key.pem
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USER=qa-mailer
SMTP_FROM_EMAIL=qa@example.com
PAYMENT_INSTAPAY_ACCOUNT=qa-synthetic-merchant
"@
[IO.File]::WriteAllText((Join-Path $taskQa 'compose.env'), $contents)
Write-Output 'Generated isolated production QA settings under .qa/production (ignored). No existing secrets overwritten.'
