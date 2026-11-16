# Wait until openfast.exe is allowed to run (Smart App Control switched off by the user), then
# generate the wind fields, run a 15-s smoke test and start the simulation queue.
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\experiment\supp_experiments\start_when_unblocked.ps1 [-Workers 12] [-MaxWaitHours 12]
# Progress: supp.log and starter_console.txt. Stop waiting: create a file named STOP in this folder.
param([int]$Workers = 12, [double]$MaxWaitHours = 12)
. D:\experiment\rosco_rerun\env_d.ps1
$root = "D:\experiment\supp_experiments"
Set-Location $root
function Log($m) { Add-Content -Encoding utf8 "$root\supp.log" "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" }
if (Test-Path "$root\STOP") { Remove-Item -LiteralPath "$root\STOP" -Confirm:$false }
foreach ($f in 'SMOKE_FAILED', 'WIND_FAILED', 'QUEUE_STARTED') { if (Test-Path "$root\$f") { Remove-Item -LiteralPath "$root\$f" -Confirm:$false } }
Set-Content -Encoding ascii "$root\starter.pid" $PID
Log "starter: waiting for openfast.exe to be allowed (pid $PID, max $MaxWaitHours h)"
$deadline = (Get-Date).AddHours($MaxWaitHours)
$ok = $false
while ((Get-Date) -lt $deadline) {
    if (Test-Path "$root\STOP") { Log "starter: STOP file found, exiting"; exit 0 }
    try {
        $out = & "$env:ROSCO_ENV\Library\bin\openfast.exe" -v 2>&1 | Out-String
        if ($out -match 'OpenFAST') { $ok = $true; break }
    } catch { }
    Start-Sleep -Seconds 20
}
if (-not $ok) { Log "starter: openfast.exe still blocked after $MaxWaitHours h, giving up"; exit 1 }
Log "starter: openfast.exe runs; generating wind fields"

cmd /c "`"$env:MAMBA_EXE`" run -p `"$env:ROSCO_ENV`" python -u prepare.py wind > starter_console.txt 2>&1"
$n = @(Get-ChildItem "$root\wind" -Recurse -Filter *.bts | Where-Object { $_.Length -gt 1MB }).Count
Log "starter: wind fields ready: $n of 9"
if ($n -lt 9) { New-Item -ItemType File -Force "$root\WIND_FAILED" | Out-Null; Log "starter: wind generation failed, see starter_console.txt and wind\*\turbsim_stdout.txt"; exit 2 }

cmd /c "`"$env:MAMBA_EXE`" run -p `"$env:ROSCO_ENV`" python -u prepare.py smoke >> starter_console.txt 2>&1"
if (-not (Select-String -Path "$root\starter_console.txt" -Pattern 'terminated normally: True' -Quiet)) {
    New-Item -ItemType File -Force "$root\SMOKE_FAILED" | Out-Null
    Log "starter: smoke test FAILED, queue not started (see starter_console.txt, runs\_smoke\openfast_stdout.txt)"
    exit 3
}
Log "starter: smoke test passed; starting queue with $Workers workers"
New-Item -ItemType File -Force "$root\QUEUE_STARTED" | Out-Null
& "$root\launch.ps1" -Workers $Workers
