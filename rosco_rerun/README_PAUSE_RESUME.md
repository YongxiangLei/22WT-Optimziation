# Chapter 6 BO rerun - pause / resume record

## Current state (2026-10-18 23:37)
- **Paused in Suspend mode**: the 6 phase-1 OpenFAST runs (baseline + eval_001..005) are frozen in RAM
  at ~51 % (≈3 320 of ≈6 700 CPU-s each). No evaluation has finished yet.
- Details: `pause_state.json`; timeline: `rerun.log`.

## Resume
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\experiment\rosco_rerun\resume.ps1
```
- If the frozen processes still exist → they are thawed and continue from ~51 % (nothing lost).
- After a **reboot / logoff** the frozen state is gone → resume.ps1 relaunches automatically:
  runs with `metrics.json` (status OK) are skipped, stored GP suggestions are reused,
  unfinished runs restart from t = 0.
- resume.ps1 also restarts the auto post-processing watcher (`auto_post.ps1`).
- Do **not** close the frozen processes in Task Manager unless you want to discard their progress.

## Pause again
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\experiment\rosco_rerun\pause.ps1            # Suspend (default)
powershell -NoProfile -ExecutionPolicy Bypass -File D:\experiment\rosco_rerun\pause.ps1 -Mode Stop # terminate
```
Suspend keeps progress but holds ~2 GB RAM; Stop frees everything but unfinished runs restart on resume.

## Run configuration (bo_rerun.py)
- Objective J: generator-power MSE vs 22 000 kW over 100–300 s (300 s simulation, DT 0.0002 s, DT_Out 0.01 s).
- Design variable ω_pc (3 values at U_pc = 12/18/24 m/s), ζ_pc fixed; bounds [0.1,0.2] [0.1,0.2] [0.1,0.5] rad/s.
- Phase 1: baseline (ROSCO default ω_pc) + 5 random points (seed 42, same as the original thesis run), 6 in parallel.
- Phase 2: 15 GP-guided evaluations in 3 rounds of 5 (Kriging Believer, UCB κ = 2.576).
- Wind: `runs\IEA-22-280-RWT\Wind\TurbSim.bts` (TurbSim SMOOTH, URef 18.2 m/s @ 170 m, seed 2318573); probe at hub height.
- ~1.9 h per OpenFAST run; remaining ≈ 1 h (phase 1) + 3 × 1.9 h ≈ 7 h after resuming.
- When finished, `auto_post.ps1` runs `postprocess.py` → `ch6_outputs\` (Table 6.2, Figs 6.2–6.5, convergence, summary.json).
- Differences from the original BO_FAST_LOG.py: `CHANGES_vs_BO_FAST_LOG.md`.

## Environment (all on D:, nothing on C:)
- micromamba `D:\software\micromamba\micromamba.exe`; env `D:\software\micromamba\envs\rosco-env`
  (Python 3.10, ROSCO 2.9.4, OpenFAST 3.5.2, bayes_opt 3.3.0; + jsonmerge, windio, orbit-nrel).
- Rebuild: `micromamba create -p <env> --file rosco-env.explicit.txt` (exact builds) or `-f rosco-env.yml`.
- `env_d.ps1` redirects TEMP/TMP/HOME/USERPROFILE/APPDATA/LOCALAPPDATA and caches to `_sys\` on D.
- Original model files are untouched: `D:\experiment\IEA-22-280-RWT-Monopile_Code\IEA-22-280-RWT-Monopile_Code`.
