# Intentional fault test on the isolated audit project ONLY. Never production.
param([string]$Docker = 'C:/Users/body/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'runtime-recovery.ps1')
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$baseline = @(Get-QARuntimeSnapshot -Docker $Docker -Project chemistryaudit2)
$observations = [System.Collections.Generic.List[object]]::new()
function Wait-QAReady([int]$Expected, [int]$Seconds) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        $result = Invoke-WebRequest -Uri 'https://localhost:18543/api/v1/ready' -SkipCertificateCheck -SkipHttpErrorCheck -TimeoutSec 5
        $observations.Add(@{utc=[DateTime]::UtcNow.ToString('o');status=$result.StatusCode;expected=$Expected})
        if ($result.StatusCode -eq $Expected) {
            if ($Expected -eq 200 -and ($result.Content | ConvertFrom-Json).status -ne 'ready') {
                throw 'Readiness200 has a wrong body'
            }
            return
        }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Readiness did not become$Expected within${Seconds}s"
}
$passed = $false
$failure = $null
$recovery = @()
try {
    Wait-QAReady 200 20
    & $Docker stop --time 10 chemistryaudit2-worker-1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not stop the exact QA worker' }
    Wait-QAReady 503 25
    $recovery = @(Restore-QARuntimeSnapshot -Docker $Docker -Snapshot $baseline)
    if (@($recovery | Where-Object started).Count -ne 1 -or
        @($recovery | Where-Object started)[0].service -ne 'worker') {
        throw 'Recovery changed more than the deliberately stopped worker'
    }
    Wait-QAReady 200 45
    $passed = $true
} catch { $failure = $_.Exception.Message }
finally {
    # A failed acceptance must not leave our deliberately stopped service down.
    try { Restore-QARuntimeSnapshot -Docker $Docker -Snapshot $baseline | Out-Null }
    catch { $passed=$false; $failure="Cleanup failed: $($_.Exception.Message)" }
    @{passed=$(if ($passed) {1} else {0});failed=$(if ($passed) {0} else {1});skipped=0;
        scope='actual QA worker interruption, exact-image recovery and HTTPS readiness';
        failure=$failure;baseline=$baseline;recovery=$recovery;observations=$observations} |
        ConvertTo-Json -Depth 8 | Tee-Object -FilePath (Join-Path $repo ".qa/audit2/runtime-recovery-live-$stamp.json")
}
if (!$passed) { throw 'Live controller recovery acceptance failed; retained JSON is authoritative' }
