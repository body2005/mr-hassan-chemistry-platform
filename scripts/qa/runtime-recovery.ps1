# Dot-source from a QA controller; no action occurs merely by loading this file.
# Preserve the originally running services if a disposable fault runner exits
# before its Python finally blocks (e.g. an explicit user cancellation).
function Get-QARuntimeSnapshot {
    param([string]$Docker, [ValidateSet('chemistryaudit2','chemistryprodlocal')][string]$Project)
    $snapshot = @()
    foreach ($service in @('postgres','redis','s3','mailpit','worker','video-worker','api','web','proxy','upload-gateway')) {
        $name = "$Project-$service-1"
        $line = & $Docker inspect $name --format '{{.Image}}|{{.State.Running}}|{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}'
        if ($LASTEXITCODE -ne 0) { throw "Missing QA runtime $service; start the isolated environment first" }
        $fields = $line.Split('|')
        if ($fields.Count -ne 4 -or $fields[0] -notmatch '^sha256:[a-f0-9]{64}$' -or
            $fields[1] -ne 'true' -or $fields[2] -ne $Project -or $fields[3] -ne $service) {
            throw "QA runtime $service is not the expected running baseline; no tests started"
        }
        $snapshot += @{name=$name;service=$service;project=$Project;image=$fields[0]}
    }
    return $snapshot
}

function Restore-QARuntimeSnapshot {
    param([string]$Docker, [object[]]$Snapshot)
    foreach ($record in $Snapshot) {
        if ($record.project -notin @('chemistryaudit2','chemistryprodlocal') -or
            $record.service -notin @('postgres','redis','s3','mailpit','worker','video-worker','api','web','proxy','upload-gateway') -or
            $record.name -ne "$($record.project)-$($record.service)-1") {
            throw 'Invalid QA recovery target; no start attempted'
        }
        $line = & $Docker inspect $record.name --format '{{.Image}}|{{.State.Running}}|{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}'
        if ($LASTEXITCODE -ne 0) { throw "QA recovery target disappeared: $($record.service); no recreation attempted" }
        $fields = $line.Split('|')
        if ($fields.Count -ne 4 -or $fields[0] -ne $record.image -or
            $fields[2] -ne $record.project -or $fields[3] -ne $record.service) {
            throw 'QA recovery target identity changed; no start attempted'
        }
        $started = $false
        if ($fields[1] -ne 'true') {
            & $Docker start $record.name | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Could not recover QA service $($record.service)" }
            $running = & $Docker inspect $record.name --format '{{.State.Running}}'
            if ($LASTEXITCODE -ne 0 -or $running -ne 'true') { throw "Recovered QA service exited: $($record.service)" }
            $started = $true
        }
        # This verifies running state, NOT readiness, test success or data safety.
        # The original failed/interrupted suite remains failed/interrupted.
        @{service=$record.service;image=$record.image;started=$started}
    }
}
