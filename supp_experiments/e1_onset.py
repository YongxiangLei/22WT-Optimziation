"""When does the large oscillation of the sweep runs start, and does it decay?"""
import glob
import os
import numpy as np
from supp_common import RUNS, SRC_RUNS, OUTB, read_outb

paths = [("0.200", os.path.join(SRC_RUNS, "sens_i1_eval_018", OUTB))] + \
        [(os.path.basename(os.path.dirname(p))[-5:], p) for p in sorted(glob.glob(os.path.join(RUNS, "sweep_w2_*", OUTB)))]
print("w2     first |rate|>=1.96 deg/s   speed std (rpm) in 25-s blocks from 0 s  | share of time at rate limit per 50 s from 0 s | t=0: speed, pitch")
for w2, p in paths:
    d = read_outb(p)
    t = d["Time"]
    pr = np.abs(np.diff(d["BldPitch1"]) / np.diff(t))
    hit = np.where(pr >= 1.96)[0]
    first = f"{t[hit[0]]:6.1f} s" if len(hit) else " never  "
    std = [np.std(d["RotSpeed"][(t >= a) & (t < a + 25)]) for a in range(0, int(t[-1]) - 24, 25)]
    sat = [100 * np.mean(pr[(t[1:] >= a) & (t[1:] < a + 50)] >= 1.96) for a in range(0, int(t[-1]) - 49, 50)]
    print(f"{w2}  {first}   " + " ".join(f"{s:.2f}" for s in std) + "  |  " + " ".join(f"{s:.0f}" for s in sat)
          + f"  | {d['RotSpeed'][0]:.2f} rpm, {d['BldPitch1'][0]:.1f} deg, speed range 0-100 s [{d['RotSpeed'][t < 100].min():.2f},{d['RotSpeed'][t < 100].max():.2f}]")
