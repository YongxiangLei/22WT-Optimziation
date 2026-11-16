# Start the second queue (run_queue2.py): it runs the simulations the first queue has not started yet on
# the idle cores. The first queue must already have its STOP file (this script does not remove it).
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\experiment\supp_experiments\launch2.ps1 -WaitPid <pid> [-Cap 16]
param([Parameter(Mandatory = $true)][string]$WaitPid, [int]$Cap = 16,      # -WaitPid "6096,31596" (one string)
      [ValidateSet('Idle', 'BelowNormal', 'Normal')][string]$Priority = 'BelowNormal')
(Get-Process -Id $PID).PriorityClass = $Priority
. D:\experiment\rosco_rerun\env_d.ps1
$root = "D:\experiment\supp_experiments"
Set-Location $root
if (Test-Path "$root\STOP2") { Remove-Item -LiteralPath "$root\STOP2" -Confirm:$false }
$con = "$root\queue2_console_$PID.txt"      # one console file per launch (an earlier launch may still hold its file)
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python -u run_queue2.py --cap $Cap --wait-pid $WaitPid *> $con
"exit=$LASTEXITCODE  $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 $con
