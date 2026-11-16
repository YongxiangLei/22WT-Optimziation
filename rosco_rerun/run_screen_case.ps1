param([string]$Case)
. D:\experiment\rosco_rerun\env_d.ps1
$d = "D:\experiment\rosco_rerun\runs\eval_017_screen_$Case"
Set-Location $d
$t0 = Get-Date
cmd /c "`"$env:MAMBA_EXE`" run -p `"$env:ROSCO_ENV`" openfast IEA-22-280-RWT-Monopile.fst > openfast_stdout.txt 2>&1"
$rc = $LASTEXITCODE
$wall = [int]((Get-Date) - $t0).TotalSeconds
$txt = Get-Content "$d\openfast_stdout.txt" -Raw
$status = if ($txt -match 'terminated normally') { 'PASSED 90 s' } elseif ($txt -match 'error at simulation time\s+([0-9.]+)') { "FAILED at t=$($Matches[1]) s" } else { "UNKNOWN (rc=$rc)" }
Add-Content -Encoding utf8 "D:\experiment\rosco_rerun\rerun.log" "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  eval_017 screening case $Case (TMax 90 s): $status, wall $wall s"
