# Repeat the three simulations stopped by the blade solver (rerun_stopped.py): 6 OpenFAST processes.
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\experiment\supp_experiments\launch_rerun.ps1
# Stop: create a file named STOP_RERUN in this folder.
param([ValidateSet('Idle', 'BelowNormal', 'Normal')][string]$Priority = 'BelowNormal')
(Get-Process -Id $PID).PriorityClass = $Priority
. D:\experiment\rosco_rerun\env_d.ps1
$root = "D:\experiment\supp_experiments"
Set-Location $root
foreach ($f in 'STOP_RERUN', 'RERUN_DONE') { if (Test-Path "$root\$f") { Remove-Item -LiteralPath "$root\$f" -Confirm:$false } }
$con = "$root\rerun_console_$PID.txt"
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python -u rerun_stopped.py *> $con
"exit=$LASTEXITCODE  $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 $con
