"""
Take over the repeated simulations (rerun_stopped.py) once they have finished:

  1. compare each repeat with the stopped run over the time both cover (largest difference of each
     channel in percent of its range) - the check that the changed coupling numerics do not alter the result;
  2. rename runs/<tag> to runs/<tag>__stopped and runs/<tag>__<variant> to runs/<tag>, so that
     postprocess_supp.py and paper_supp.py use the completed run (nothing is deleted).

  python promote_rerun.py            (dry run: comparison only)
  python promote_rerun.py --apply
"""
import json
import os
import sys

import numpy as np
from supp_common import RUNS, OUTB, read_outb

CASES = ["val_U22_s1_default", "val_U14_s3_opt", "sweep_w2_0.250"]
CH = ["GenPwr", "RotSpeed", "BldPitch1", "GenTq", "TwrBsMyt", "B1RootMyr", "B1TipTDxr", "RotThrust"]
apply = "--apply" in sys.argv

for tag in CASES:
    done = None
    for var in ("r2", "c1"):
        m = os.path.join(RUNS, f"{tag}__{var}", "metrics.json")
        if os.path.exists(m) and json.load(open(m)).get("status") == "OK":
            done = var
            break
    if done is None:
        print(f"{tag}: no finished repeat yet")
        continue
    new_dir, old_dir = os.path.join(RUNS, f"{tag}__{done}"), os.path.join(RUNS, tag)
    a, b = read_outb(os.path.join(old_dir, OUTB)), read_outb(os.path.join(new_dir, OUTB))
    n = min(len(a["Time"]), len(b["Time"]))
    t_end = a["Time"][n - 1]
    worst = {}
    for ch in CH:
        rng = np.ptp(b[ch][:n])
        d = np.abs(a[ch][:n] - b[ch][:n])
        worst[ch] = (100 * d.max() / rng, 100 * d[a["Time"][:n] <= t_end - 5].max() / rng)
    w = (a["Time"][:n] >= 100)
    ja = np.mean((a["GenPwr"][:n][w] - 22000.0) ** 2) if w.sum() > 100 else float("nan")
    jb = np.mean((b["GenPwr"][:n][w] - 22000.0) ** 2) if w.sum() > 100 else float("nan")
    print(f"{tag}: repeat '{done}' finished ({b['Time'][-1]:.0f} s); overlap 0-{t_end:.1f} s")
    print("   largest difference in % of the channel range (whole overlap / without the last 5 s before the stop):")
    print("   " + "  ".join(f"{ch} {v[0]:.3f}/{v[1]:.3f}" for ch, v in worst.items()))
    print(f"   J over 100 s .. end of overlap: stopped run {ja / 1e3:.4f}, repeat {jb / 1e3:.4f} (x 1e3 kW2), difference {100 * (jb / ja - 1):+.4f} %")
    if apply:
        os.rename(old_dir, old_dir + "__stopped")
        os.rename(new_dir, old_dir)
        print(f"   promoted: runs/{tag}__{done} -> runs/{tag}; stopped run kept as runs/{tag}__stopped")
