# bo_rerun.py vs. the original Chapter 6 code (BO_FAST_LOG.py)

Original: `D:\experiment\IEA-22-280-RWT-Monopile_Code\IEA-22-280-RWT-Monopile_Code\BO_FAST_LOG.py`
(run 2025-09-15 → 2025-09-17, log `optimization.log`, per-iteration files in `iterations\`).
Rerun:    `D:\experiment\rosco_rerun\bo_rerun.py`.

## Unchanged
- Design variable: ω_pc at the three ROSCO breakpoints U_pc = 12 / 18 / 24 m/s; ζ_pc fixed
  ([0.847, 1.756, 0.744]); other ROSCO settings from `IEA-22-280-RWT-Monopile.yaml`.
- Bounds: ω_pc1 ∈ [0.1, 0.2], ω_pc2 ∈ [0.1, 0.2], ω_pc3 ∈ [0.1, 0.5] rad/s.
- Pipeline per candidate: `load_rosco_yaml` → `Turbine.load_from_fast` → `Controller.tune_controller`
  (Kp = (2ζω + A)/B, Ki = ω²/B) → `write_DISCON` → OpenFAST → power MSE vs 22 000 kW.
- Turbine model, 300 s simulation (TMax), DT = 0.0002 s, wind field `TurbSim.bts`.
- 5 random initial points with seed 42: identical to iterations 1–5 of the original run.

## Changed (and why)
| Item | BO_FAST_LOG.py | bo_rerun.py | Reason |
|---|---|---|---|
| Objective window | last 500 samples = last 0.1 s (DT_Out = 0.0002 s) | 100–300 s | J measured one instant (viva 5) |
| Baseline | not run | ROSCO default ω_pc, same J | baseline MSE missing (viva 4) |
| BO budget | 5 random + 5 GP (sequential) | 5 random + 15 GP, 3 rounds × 5 in parallel (Kriging Believer) | non-converged; run time |
| Acquisition | bayes_opt default (version not recorded) | bayes_opt 3.3.0 default UCB, κ = 2.576 | documented |
| Run directories | shared; outb / DISCON overwritten | one directory per evaluation | traceability of Figs 6.3–6.5 |
| Output step | DT_Out default (0.0002 s), 213 MB/run | 0.01 s, ~4 MB/run | size only; no effect on dynamics |
| Wind probe | z = 310 m (WindVziList) | z = 170 m (hub height) | Fig 6.2 shows hub-height wind; output only |
| ROSCO LoggingLevel | 2 | 0 | debug files only; no effect on control |
| Software | OpenFAST 3.5.0, ROSCO 2.9.4 | OpenFAST 3.5.2, ROSCO 2.9.4 | 3.5.0 not available for win-64 on conda-forge |
| Paths | `openfast_x64.exe`, `E:\...\libdiscon.dll`, `E:\...\TurbSim.bts` | env binaries on D:, local copy of the same .bts | E: drive not present |
| Extra metrics | – | RMSE, gen-speed MSE, pitch std/travel, TwrBsMyt std, old last-0.1 s J | discussion / comparison |
