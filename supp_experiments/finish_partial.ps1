# After a planned stop (STOP / STOP2): wait until the simulations that are still running have finished,
# save the results obtained so far (postprocess_supp.py -> outputs\), and shut the computer down.
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\experiment\supp_experiments\finish_partial.ps1 -QueuePids 6096,31596
# Requested by the user on 2026-11-13: finish the running simulations, save, continue the rest next time.
# No shutdown if a file named NO_SHUTDOWN exists in this folder; during the 5-minute warning: shutdown /a
param([Parameter(Mandatory = $true)][string]$QueuePids, [double]$MaxWaitHours = 12, [switch]$NoShutdown)
$root = "D:\experiment\supp_experiments"
function Log($m) { Add-Content -Encoding utf8 "$root\supp.log" "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" }
# -File passes "6096,31596" as one string, so the list is split here; every pid must be a live python
# queue at start, otherwise nothing is done (a wrong list would otherwise look like "all finished").
[int[]]$QueuePids = $QueuePids -split '[,; ]+' | Where-Object { $_ }
foreach ($q in $QueuePids) {
    $pr = Get-CimInstance Win32_Process -Filter "ProcessId = $q"
    if (-not $pr -or $pr.Name -notlike 'python*') { Log "finisher: pid $q is not a running queue, exiting without doing anything"; exit 3 }
}
Set-Content -Encoding ascii "$root\shutdown_watch.pid" $PID
Log "finisher started (pid $PID): waits for queues $($QueuePids -join ', '), then saves the partial results and shuts down"
$deadline = (Get-Date).AddHours($MaxWaitHours)
while ($true) {
    $alive = @($QueuePids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
    $sims = @(Get-CimInstance Win32_Process -Filter "Name = 'openfast.exe'" | Where-Object { $QueuePids -contains $_.ParentProcessId })
    if ($alive.Count -eq 0 -and $sims.Count -eq 0) { break }
    if ((Get-Date) -gt $deadline) { Log "finisher: still running after $MaxWaitHours h, exiting without saving or shutdown"; exit 1 }
    Start-Sleep -Seconds 60
}
. D:\experiment\rosco_rerun\env_d.ps1
Set-Location $root
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python postprocess_supp.py *> "$root\postprocess_console.txt"
$rc = $LASTEXITCODE
$ok = @(Get-ChildItem "$root\runs" -Directory | Where-Object { (Test-Path "$($_.FullName)\metrics.json") -and ((Get-Content "$($_.FullName)\metrics.json" -Raw) -match '"status": "OK"') }).Count
Log "finisher: running simulations finished; postprocess_supp.py exit=$rc; $ok runs with status OK; results in outputs\supp_summary.json"
Set-Content -Encoding ascii "$root\PARTIAL_DONE" (Get-Date -Format s)
if ($NoShutdown -or (Test-Path "$root\NO_SHUTDOWN")) { Log "finisher: no shutdown requested, exiting"; exit 0 }
Log "finisher: shutting down in 5 min"
shutdown.exe /s /t 300 /c "Running simulations finished and results saved (D:\experiment\supp_experiments). Shutting down in 5 minutes; run 'shutdown /a' to cancel."
