"""Print the validation pairs that are available so far (reads outputs/supp_summary.json)."""
import json
import os
import numpy as np
from supp_common import OUT, RUNS, read_outb

s = json.load(open(os.path.join(OUT, "supp_summary.json")))
e = s["E2_validation"]
K = [("J_power_mse_kW2", "J"), ("genspd_rmse_rpm", "speed"), ("pitch_travel_degps", "travel"), ("twr_fa_std_kNm", "FAstd"),
     ("twr_fa_del_kNm", "FAdel"), ("twr_ss_del_kNm", "SSdel"), ("bld_flap_del_kNm", "flapDEL"), ("thrust_std_kN", "thrust"),
     ("overspeed_pct", "overspd")]
print("incomplete:", [(p["U"], p["seed"]) for p in e["incomplete"]], " truncated:", e["truncated"])
print("U seed  Jdef    Jopt   | change in % : " + "  ".join(n for _, n in K[:-1]) + " | overspeed def/opt %")
for p in e["pairs"]:
    print(f"{p['U']:2d} {p['seed']}  {p['default']['J_power_mse_kW2'] / 1e3:7.2f} {p['opt']['J_power_mse_kW2'] / 1e3:7.2f} | "
          + "  ".join(f"{p['change_pct'][k]:+6.1f}" for k, _ in K[:-1])
          + f" | {p['default']['overspeed_pct']:.1f} / {p['opt']['overspeed_pct']:.1f}")
for u, v in e["by_U"].items():
    print(f"mean U={u} (n={v['n']}): " + "  ".join(f"{n} {v['change_pct_mean'][k]:+.1f}" for k, n in K[:-1]))
if "all" in e:
    print(f"all (n={e['all']['n']}): " + "  ".join(f"{n} {e['all']['change_pct_mean'][k]:+.1f}" for k, n in K[:-1]))
    print("improved in:", {n: e["all"]["n_improved"][k] for k, n in K[:-1]})

# where does the large J of the default controller on U14 seed 3 come from?
for c in ("default", "opt"):
    d = read_outb(os.path.join(RUNS, f"val_U14_s3_{c}", "IEA-22-280-RWT-Monopile.outb"))
    t, p, u = d["Time"], d["GenPwr"], d["Wind1VelX"]
    w = (t >= 100) & (t <= 644)
    err2 = (p[w] - 22000.0) ** 2
    blk = [(a, float(err2[(t[w] >= a) & (t[w] < a + 50)].mean()) / 1e3) for a in range(100, 640, 50)]
    low = p[w] < 21500
    print(f"U14 s3 {c}: min power {p[w].min():.0f} kW at t={t[w][np.argmin(p[w])]:.1f} s, time with P<21.5 MW {low.mean() * 544:.1f} s, "
          f"min wind {u[w].min():.1f}, min rotor speed {d['RotSpeed'][w].min():.2f} rpm")
    print("   J per 50-s block (1e3 kW2):", " ".join(f"{a}:{v:.1f}" for a, v in blk))
