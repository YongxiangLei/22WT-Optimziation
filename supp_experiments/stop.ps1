# Stop the supplementary simulation queue.
#   stop.ps1            no new simulation starts; the running ones finish (up to ~6 h)
#   stop.ps1 -Kill      additionally terminates the running OpenFAST processes of this queue;
#                       their progress is lost and they restart from t = 0 on the next launch.ps1
param([switch]$Kill)
$root = "D:\experiment\supp_experiments"
New-Item -ItemType File -Force "$root\STOP" | Out-Null
New-Item -ItemType File -Force "$root\STOP2" | Out-Null      # stop file of the second queue (run_queue2.py)
"STOP file written: no new simulation will start."
if ($Kill) {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'openfast.exe'" |
        Where-Object { $_.ExecutablePath -like "D:\software\micromamba\envs\rosco-env\*" }
    foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -Confirm:$false; "terminated openfast pid $($p.ProcessId)" }
    "Restart later with launch.ps1 (finished runs are kept)."
}
