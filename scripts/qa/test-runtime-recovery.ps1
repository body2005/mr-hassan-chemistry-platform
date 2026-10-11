# Controller unit regressions; no Docker daemon, secrets or live mutations.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'runtime-recovery.ps1')
$taskServices = @('postgres','redis','s3','mailpit','worker','video-worker','api','web','proxy','upload-gateway')
$taskImage = 'sha256:' + ('a' * 64)
$script:taskContainers = @{}
$script:taskStarts = [System.Collections.Generic.List[string]]::new()
foreach ($service in $taskServices) {
    $script:taskContainers["chemistryaudit2-$service-1"] = @{image=$taskImage;running=$true;project='chemistryaudit2';service=$service}
}
function Invoke-MockDocker {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
    $global:LASTEXITCODE = 0
    $target = $script:taskContainers[$Arguments[1]]
    if (!$target) { $global:LASTEXITCODE=1; return }
    if ($Arguments[0] -eq 'start') {
        $script:taskStarts.Add($Arguments[1])
        $target.running = $true
        return $Arguments[1]
    }
    if ($Arguments[0] -ne 'inspect') { throw 'Unexpected mock operation' }
    $running = "$($target.running)".ToLowerInvariant()
    if ($Arguments[-1] -eq '{{.State.Running}}') { return $running }
    return "$($target.image)|$running|$($target.project)|$($target.service)"
}
function Assert-QA([bool]$Condition, [string]$Message) {
    if (!$Condition) { throw $Message }
}
$passed = 0
$baseline = @(Get-QARuntimeSnapshot -Docker Invoke-MockDocker -Project chemistryaudit2)
Assert-QA ($baseline.Count -eq 10) 'Baseline omits a required service'
$unchanged = @(Restore-QARuntimeSnapshot -Docker Invoke-MockDocker -Snapshot $baseline)
Assert-QA ($unchanged.Count -eq 10 -and $script:taskStarts.Count -eq 0) 'Running services were restarted'
$passed++

$worker = $script:taskContainers['chemistryaudit2-worker-1']
$worker.running = $false
$recovered = @(Restore-QARuntimeSnapshot -Docker Invoke-MockDocker -Snapshot $baseline)
Assert-QA ($worker.running -and $script:taskStarts.Count -eq 1 -and $script:taskStarts[0] -eq 'chemistryaudit2-worker-1') 'Recovery broadened targets'
Assert-QA (@($recovered | Where-Object started).Count -eq 1) 'Recovery metadata is incorrect'
$passed++

$worker.running = $false
$caught = $null
try {
    try { throw 'synthetic interrupted suite' }
    finally { Restore-QARuntimeSnapshot -Docker Invoke-MockDocker -Snapshot $baseline | Out-Null }
} catch { $caught = $_.Exception.Message }
Assert-QA ($caught -eq 'synthetic interrupted suite' -and $worker.running) 'Cleanup hid the interrupted suite'
$passed++

foreach ($field in @('project','image','service')) {
    $saved = $worker[$field]
    $worker.running = $false
    $worker[$field] = 'changed'
    $before = $script:taskStarts.Count
    $rejected = $false
    try { Restore-QARuntimeSnapshot -Docker Invoke-MockDocker -Snapshot $baseline | Out-Null }
    catch { $rejected = $true }
    Assert-QA ($rejected -and $script:taskStarts.Count -eq $before) "Changed $field was started"
    $worker[$field] = $saved
    $worker.running = $true
    $passed++
}

$rejected = $false
try { Restore-QARuntimeSnapshot -Docker Invoke-MockDocker -Snapshot @(@{project='chemistryaudit2';service='postgres-restore';name='chemistryaudit2-postgres-restore-1';image=$taskImage}) | Out-Null }
catch { $rejected = $true }
Assert-QA $rejected 'Unknown restore service accepted'
$passed++

$worker.running = $false
$before = $script:taskStarts.Count
$rejected = $false
try { Get-QARuntimeSnapshot -Docker Invoke-MockDocker -Project chemistryaudit2 | Out-Null }
catch { $rejected = $true }
Assert-QA ($rejected -and $script:taskStarts.Count -eq $before) 'Stopped baseline silently changed'
$worker.running = $true
$passed++

$script:taskContainers.Remove('chemistryaudit2-worker-1')
$before = $script:taskStarts.Count
$rejected = $false
try { Restore-QARuntimeSnapshot -Docker Invoke-MockDocker -Snapshot $baseline | Out-Null }
catch { $rejected = $true }
Assert-QA ($rejected -and $script:taskStarts.Count -eq $before) 'Missing service recreated'
$passed++
@{passed=$passed;failed=0;skipped=0;scope='controller mocks only; no live readiness claim'} | ConvertTo-Json -Compress
