"""A few numbers over the 35 simulated candidates (20 optimization + 15 random) for the manuscript."""
import json
import os
import numpy as np
from supp_common import RUNS, SRC_RUNS, ref_metrics

bo = [ref_metrics(f"eval_{i:03d}") for i in range(1, 21)]
om = [json.load(open(os.path.join(SRC_RUNS, f"eval_{i:03d}", "parameters.json")))["omega_pc"] for i in range(1, 21)]
rnd = [json.load(open(os.path.join(RUNS, f"rand_{i:03d}", "metrics.json"))) for i in range(6, 21)]
W = np.array(om + [m["omega_pc"] for m in rnd])
allm = bo + rnd
for k in ("J_power_mse_kW2", "genspd_rmse_rpm", "pitch_travel_deg", "twr_fa_std_kNm", "twr_fa_del_kNm"):
    y = np.array([m[k] for m in allm])
    print(f"{k:20s} corr with w1 {np.corrcoef(W[:, 0], y)[0, 1]:+.2f}  w2 {np.corrcoef(W[:, 1], y)[0, 1]:+.2f}  w3 {np.corrcoef(W[:, 2], y)[0, 1]:+.2f}"
          f"   range {y.min():.4g} .. {y.max():.4g}")
base = ref_metrics("baseline")
J = np.array([m["J_power_mse_kW2"] for m in allm])
print("candidates better than default:", int((J < base["J_power_mse_kW2"]).sum()), "of", len(J))
hi = W[:, 1] >= 0.175
print("w2 >= 0.175:", int(hi.sum()), " J range", J[hi].min() / 1e3, J[hi].max() / 1e3, " | w2 < 0.14:", int((W[:, 1] < 0.14).sum()),
      J[W[:, 1] < 0.14].min() / 1e3, J[W[:, 1] < 0.14].max() / 1e3)
