# Bayesian optimization of the pitch controller of the IEA 22-MW offshore wind turbine

Batch Bayesian optimization of the collective pitch controller (ROSCO) of the IEA Wind 22-MW
monopile reference turbine with the OpenFAST model in the loop: optimization code, simulation
inputs, post-processing, and derived results.

## Layout

| Folder | Content |
|---|---|
| `rosco_rerun/` | The optimization: baseline and 20 candidates (5 random, 3 batches of 5), 300 s each. `bo_rerun.py` runs it, `postprocess.py` and `extra_analysis.py` evaluate it, `ch6_outputs/` holds the result tables and figures. `runs/<case>/` holds the inputs, the solver log, the gain schedule, and the metrics of every case. |
| `supp_experiments/` | Supplementary simulations (42 cases): sweep of the natural frequency at 18 m/s beyond the search bound, validation on nine IEC class-B wind fields at 14, 18, and 22 m/s, and random search with the same budget. `prepare.py` builds the cases, `run_queue.py` runs them, `postprocess_supp.py` and `paper_supp.py` evaluate them, `posthoc_analysis.py` does the frequency-band and reproducibility analysis, and `fig3d.py`, `fig_power.py`, `fig_basic.py` draw the figures. `outputs/` holds the result tables and figure previews. |
| `ch6_check/` | A small script for checking binary output files. |

## Not in the repository

These files are excluded by `.gitignore` because of their size. They can be regenerated.

| Files | Size | How to obtain them |
|---|---|---|
| Binary time series of the simulations (`*.outb`) | about 380 MB | Rerun the cases; every `runs/<case>/` folder contains the complete input set. The figure scripts read these files. |
| Turbulent wind fields (`*.bts`) | about 840 MB | TurbSim with the `*.inp` files in `supp_experiments/wind/`; the tuning wind field belongs to the turbine model. |
| OpenFAST and TurbSim executables | | Installed from conda-forge, see below. |

## Environment

- OpenFAST 3.5.2, ROSCO 2.9, Python with `bayes_opt` 3.3.0; the conda environment is specified in
  `rosco_rerun/rosco-env.yml` (exact package list: `rosco_rerun/rosco-env.explicit.txt`).
- The scripts were written for Windows and use absolute paths on drive `D:` (`D:\experiment\...`);
  adjust `rosco_rerun/env_d.ps1` and the path constants at the top of the scripts for another machine.
  The figure scripts write to a folder outside the repository (constant `PAPER`).
- One 300-s simulation of the model with BeamDyn blades takes about 2 h on one core.

## Reproducing the results

With the binary outputs in place:

```powershell
python rosco_rerun\postprocess.py              # tables and figures of the optimization
python supp_experiments\posthoc_analysis.py    # frequency bands, reproducibility, trade-off
python supp_experiments\postprocess_supp.py    # metrics of the supplementary cases
python supp_experiments\paper_supp.py          # all numbers of the sweep, validation, random search
python supp_experiments\fig3d.py               # response surfaces and rotor-speed waterfall
```

The derived results are also stored: `rosco_rerun/results.csv`, `rosco_rerun/final_results.json`,
`rosco_rerun/ch6_outputs/`, `supp_experiments/outputs/`, and one `metrics.json` per case.

## Model and software

The turbine model is the IEA Wind 22-MW offshore reference turbine (monopile configuration),
simulated with OpenFAST and controlled by ROSCO; the input files in the `runs/` folders are derived
from the public model files. Please cite the original sources when using them.
