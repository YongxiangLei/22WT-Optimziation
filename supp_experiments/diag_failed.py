"""Look at the last seconds of runs that ended with a BeamDyn convergence error."""
import os
import sys
import numpy as np
from supp_common import read_outb

ROOT = os.path.dirname(os.path.abspath(__file__))
CH = ["Wind1VelX", "RotSpeed", "GenPwr", "GenTq", "BldPitch1", "TwrBsMyt", "B1RootMyr"]


def show(tag, others=()):
    d = read_outb(os.path.join(ROOT, "runs", tag, "IEA-22-280-RWT-Monopile.outb"))
    t = d["Time"]
    print(f"=== {tag}: {len(t)} samples, t = {t[0]:.2f} .. {t[-1]:.2f} s, dt_out = {t[1] - t[0]:.4f}")
    extra = [k for k in d if any(s in k for s in ("TipTD", "TipD", "TDxr", "TDyr", "RootMxr", "RootMzr"))]
    if tag == sys.argv[1]:
        print("channels:", ", ".join(k for k in d if k != "Time"))
    te = t[-1]
    for lab, a, b in (("whole (>=100 s)", 100.0, te - 20), ("last 20-5 s", te - 20, te - 5), ("last 5-1 s", te - 5, te - 1),
                      ("last 1 s", te - 1, te)):
        w = (t >= a) & (t <= b)
        if w.sum() < 2:
            continue
        print(f"  {lab:16s}", "  ".join(
            f"{c}: {d[c][w].mean():.4g} [{d[c][w].min():.4g},{d[c][w].max():.4g}]" for c in CH + extra if c in d))
    pr = np.diff(d["BldPitch1"]) / np.diff(t)
    print(f"  max |pitch rate| overall {np.abs(pr).max():.2f} deg/s, in last 5 s {np.abs(pr[t[1:] > te - 5]).max():.2f} deg/s")
    for o in others:
        p = os.path.join(ROOT, "runs", o, "IEA-22-280-RWT-Monopile.outb")
        if not os.path.exists(p):
            continue
        e = read_outb(p)
        w = (e["Time"] >= te - 5) & (e["Time"] <= te)
        if w.sum() > 2:
            print(f"  partner {o} in the same last 5 s:", "  ".join(
                f"{c}: {e[c][w].mean():.4g} [{e[c][w].min():.4g},{e[c][w].max():.4g}]" for c in CH if c in e))


if __name__ == "__main__":
    show(sys.argv[1], sys.argv[2:])
