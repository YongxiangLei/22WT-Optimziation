# Start (or restart) the supplementary simulation queue. Finished runs are skipped.
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\experiment\supp_experiments\launch.ps1 [-Workers 8] [-Priority BelowNormal]
# -Workers  : number of simulations that run at the same time (one core each)
# -Priority : Windows priority class of the simulations (BelowNormal keeps the desktop responsive)
param([int]$Workers = 8, [ValidateSet('Idle', 'BelowNormal', 'Normal')][string]$Priority = 'BelowNormal')
(Get-Process -Id $PID).PriorityClass = $Priority      # child processes inherit Idle / BelowNormal
. D:\experiment\rosco_rerun\env_d.ps1
$root = "D:\experiment\supp_experiments"
Set-Location $root
foreach ($f in 'STOP', 'STOP2', 'PARTIAL_DONE') { if (Test-Path "$root\$f") { Remove-Item -LiteralPath "$root\$f" -Confirm:$false } }
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python -u run_queue.py --workers $Workers *> "$root\queue_console.txt"
"exit=$LASTEXITCODE  $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 "$root\queue_console.txt"
