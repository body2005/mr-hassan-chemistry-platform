param([string]$Docker='C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$fixture=Join-Path $taskRoot ('.qa/audit2/backup-permissions-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture | Out-Null
$image='python:3.12.15-slim-trixie@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016'
$helper=Join-Path $taskRoot 'infra/backup-permissions.sh'
$records=[System.Collections.Generic.List[object]]::new()
function Run-Check([string]$label,[string[]]$arguments,[int]$expected=0) {
    & $Docker @arguments
    $code=$LASTEXITCODE
    $records.Add(@{command=$label;exit_code=$code;expected_exit=$expected;passed=($code -eq $expected)})
    $records | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $fixture 'commands.json') -Encoding utf8
    if($code -ne $expected){throw "Backup permission regression '$label': actual $code expected $expected"}
}
$base=@('run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--entrypoint','/bin/sh')
foreach($case in @('valid','symlink','file')) {
    $directory=Join-Path $fixture $case
    New-Item -ItemType Directory -Path $directory | Out-Null
    $mounted=$base+@('--user','0:0','--cap-add','CHOWN','--cap-add','DAC_OVERRIDE','--cap-add','FOWNER','-v',"${directory}:/backups",'-v',"${helper}:/helper.sh:ro")
    if($case -eq 'valid') {
        Run-Check 'fixture legacy root-owned 755 directories' ($mounted+@($image,'-ec','mkdir /backups/s3; chown 0:0 /backups /backups/s3; chmod 755 /backups /backups/s3; echo preserve > /backups/s3/existing; chmod 644 /backups/s3/existing'))
        Run-Check 'UID 10001 fails BEFORE fix' ($base+@('--user','10001:10001','-v',"${directory}:/backups",$image,'-ec','touch /backups/s3/probe')) 1
        Run-Check 'production helper migrates ONLY two directories' ($mounted+@($image,'/helper.sh'))
        Run-Check 'UID 10001 writes AFTER fix with private modes; old contents unchanged' ($base+@('--user','10001:10001','-v',"${directory}:/backups",$image,'-ec','test "$(stat -c "%a %u:%g" /backups)" = "750 10001:10001"; test "$(stat -c "%a %u:%g" /backups/s3)" = "750 10001:10001"; umask 077; echo probe > /backups/s3/probe; test "$(stat -c %a /backups/s3/probe)" = 600; test "$(cat /backups/s3/existing)" = preserve; test "$(stat -c "%a %u:%g" /backups/s3/existing)" = "644 0:0"'))
    } else {
        $setup=if($case -eq 'symlink'){'mkdir /backups/outside; echo preserve > /backups/outside/sentinel; ln -s /backups/outside /backups/s3'}else{'echo preserve > /backups/s3'}
        Run-Check "$case negative fixture" ($mounted+@($image,'-ec',"$setup; chown 0:0 /backups; chmod 755 /backups"))
        Run-Check "$case rejected BEFORE metadata changes" ($mounted+@($image,'/helper.sh')) 1
        $verify=if($case -eq 'symlink'){'test -L /backups/s3; test "$(cat /backups/outside/sentinel)" = preserve; test "$(stat -c "%a %u:%g" /backups/outside)" = "755 0:0"'}else{'test -f /backups/s3; test "$(cat /backups/s3)" = preserve'}
        Run-Check "$case contents and parent metadata unchanged" ($mounted+@($image,'-ec',"test `"`$(stat -c '%a %u:%g' /backups)`" = '755 0:0'; $verify"))
    }
}
Write-Output "Backup permissions: 3 cases passed, 0 failed, 0 skipped. Fixtures retained: $fixture"
