"""Sweep runs evaluated on later windows, after the start-up oscillation has decayed."""
import os
import numpy as np
from supp_common import RUNS, SRC_RUNS, OUTB, read_outb

runs = [("default", os.path.join(SRC_RUNS, "sens_i1_baseline", OUTB)), ("0.100", os.path.join(RUNS, "sweep_w2_0.100", OUTB)),
        ("0.150", os.path.join(RUNS, "sweep_w2_0.150", OUTB)), ("0.200", os.path.join(SRC_RUNS, "sens_i1_eval_018", OUTB)),
        ("0.240", os.path.join(RUNS, "sweep_w2_0.240", OUTB)), ("0.260", os.path.join(RUNS, "sweep_w2_0.260", OUTB))]
print("run      | J (1e3 kW2), speed RMSE (rpm), tower FA std (MNm), pitch travel (deg) on 100-300 | 150-300 | 200-300 | 250-300 s")
for name, p in runs:
    d = read_outb(p)
    t = d["Time"]
    out = []
    for a in (100, 150, 200, 250):
        w = t >= a
        out.append("%7.2f %.3f %6.2f %6.1f" % (np.mean((d["GenPwr"][w] - 22000.0) ** 2) / 1e3, np.sqrt(np.mean((d["RotSpeed"][w] - 7.0611) ** 2)),
                                              np.std(d["TwrBsMyt"][w]) / 1e3, np.sum(np.abs(np.diff(d["BldPitch1"][w])))))
    print(f"{name:8s} | " + " | ".join(out))
