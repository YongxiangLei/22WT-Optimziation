. D:\experiment\rosco_rerun\env_d.ps1
Set-Location D:\experiment\rosco_rerun
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python -u bo_rerun.py run --n-iter 15 --batch 5 *> D:\experiment\rosco_rerun\rerun_console.txt
"exit=$LASTEXITCODE  $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 D:\experiment\rosco_rerun\rerun_console.txt
