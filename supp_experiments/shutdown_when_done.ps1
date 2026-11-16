# Shut the computer down after the simulation queue has finished (requested by the user on 2026-11-13).
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\experiment\supp_experiments\shutdown_when_done.ps1
# Sequence:
#   1. wait until DONE exists (written by run_queue.py when all 40 runs have been processed);
#   2. wait up to -GraceMinutes for MANUSCRIPT_UPDATED (written once the results are in the manuscript);
#   3. shutdown /s with a 5-minute warning. Abort during the warning with:  shutdown /a
# Cancel the whole thing at any time: create a file named NO_SHUTDOWN in this folder, or stop this process
# (pid in shutdown_watch.pid). If the queue ends without DONE (stopped or crashed), nothing is shut down.
param([double]$MaxWaitHours = 40, [int]$GraceMinutes = 90)
$root = "D:\experiment\supp_experiments"
function Log($m) { Add-Content -Encoding utf8 "$root\supp.log" "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" }
Set-Content -Encoding ascii "$root\shutdown_watch.pid" $PID
Log "shutdown watcher started (pid $PID): shuts down after DONE, at the latest $GraceMinutes min later"
$deadline = (Get-Date).AddHours($MaxWaitHours)
while (-not (Test-Path "$root\DONE")) {
    if (Test-Path "$root\NO_SHUTDOWN") { Log "shutdown watcher: NO_SHUTDOWN found, exiting"; exit 0 }
    if ((Get-Date) -gt $deadline) { Log "shutdown watcher: queue not finished after $MaxWaitHours h, exiting without shutdown"; exit 1 }
    $qpid = Get-Content "$root\queue.pid" -ErrorAction SilentlyContinue
    if ($qpid -and -not (Get-Process -Id $qpid -ErrorAction SilentlyContinue)) {
        Start-Sleep -Seconds 120
        if (-not (Test-Path "$root\DONE")) { Log "shutdown watcher: queue process ended without DONE, exiting without shutdown"; exit 2 }
    }
    Start-Sleep -Seconds 60
}
Log "shutdown watcher: DONE found; waiting up to $GraceMinutes min for MANUSCRIPT_UPDATED"
$grace = (Get-Date).AddMinutes($GraceMinutes)
while (-not (Test-Path "$root\MANUSCRIPT_UPDATED") -and (Get-Date) -lt $grace) {
    if (Test-Path "$root\NO_SHUTDOWN") { Log "shutdown watcher: NO_SHUTDOWN found, exiting"; exit 0 }
    Start-Sleep -Seconds 30
}
if (Test-Path "$root\NO_SHUTDOWN") { Log "shutdown watcher: NO_SHUTDOWN found, exiting"; exit 0 }
Log ("shutdown watcher: shutting down in 5 min (manuscript updated: " + (Test-Path "$root\MANUSCRIPT_UPDATED") + ")")
shutdown.exe /s /t 300 /c "Supplementary simulations finished (D:\experiment\supp_experiments). Shutting down in 5 minutes; run 'shutdown /a' to cancel."
