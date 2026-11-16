"""Numbers and pgfplots data of the supplementary experiments E1-E3 for the manuscript.
Writes CSV files (column names without underscores) to paper_ieee_draft/figures/data and prints the tables."""
import json
import os
import numpy as np
from supp_common import ROOT, RUNS, SRC_RUNS, OUT, OUTB, read_outb, ref_metrics, metrics

PAPER = r"D:\experiment\paper_ieee_draft\figures\data"
S = json.load(open(os.path.join(OUT, "supp_summary.json")))
print("n_ok", S["n_ok"], "of", S["n_jobs"], "missing/failed:", S["missing_or_failed"])


def wcsv(name, header, rows):
    with open(os.path.join(PAPER, name), "w") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(f"{x:.6g}" if isinstance(x, (float, np.floating)) else str(x) for x in r) + "\n")
    print("wrote", name, len(rows), "rows")


def sat_share(path, lim=2.0):
    d = read_outb(path)
    t = d["Time"]
    pr = np.abs(np.diff(d["BldPitch1"]) / np.diff(t))[t[1:] >= 100]
    return float(np.mean(pr >= 0.98 * lim) * 100)


# ---------------------------------------------------------------- E1
base = ref_metrics("sens_i1_baseline")
print("\nE1 sweep (default: J %.2f, speed %.3f, travel %.1f, FA std %.2f, FA DEL %.2f, max speed %.2f)" % (
    base["J_power_mse_kW2"] / 1e3, base["genspd_rmse_rpm"], base["pitch_travel_deg"], base["twr_fa_std_kNm"] / 1e3,
    base["twr_fa_del_kNm"] / 1e3, base["genspd_max_rpm"]))
rows = []
tags = [("sens_i1_eval_018", None)] + [(j["tag"], j) for j in json.load(open(os.path.join(ROOT, "jobs.json"))) if j["group"] == "E1_sweep"]
for tag, j in tags:
    if j is None:
        m = ref_metrics(tag); path = os.path.join(SRC_RUNS, tag, OUTB); w2 = m["omega_pc"][1] if "omega_pc" in m else 0.2
    else:
        p = os.path.join(RUNS, tag, "metrics.json")
        m = json.load(open(p))
        if m.get("status") != "OK":
            print(f"  {tag}: {m.get('status')}"); continue
        path = os.path.join(RUNS, tag, OUTB); w2 = m["omega_pc"][1]
    rows.append([w2, m["J_power_mse_kW2"] / 1e3, m["power_rmse_kW"], m["genspd_rmse_rpm"], m["genspd_min_rpm"], m["genspd_max_rpm"],
                 m["pitch_travel_deg"], m["pitch_rate_max_degps"], sat_share(path), m["twr_fa_std_kNm"] / 1e3, m["twr_fa_del_kNm"] / 1e3,
                 m["power_maxdev_kW"]])
rows.sort()
print("  w2     J(1e3)   Prmse  spdRMSE  spd_min spd_max  travel  maxrate  sat%   FAstd   FAdel  maxdevP")
for r in rows:
    print("  %.3f %9.2f %7.1f %7.3f %7.2f %7.2f %7.1f %7.2f %6.1f %7.2f %7.2f %7.0f" % tuple(r))
wcsv("sweep.csv", ["w2", "J", "prmse", "spd", "spdmin", "spdmax", "travel", "maxrate", "sat", "fastd", "fadel", "maxdev"], rows)

# ---------------------------------------------------------------- E2
e = S["E2_validation"]
K = ["J_power_mse_kW2", "genspd_rmse_rpm", "pitch_travel_degps", "twr_fa_std_kNm", "twr_fa_del_kNm", "twr_ss_del_kNm", "bld_flap_del_kNm", "overspeed_pct"]
print("\nE2 incomplete:", e["incomplete"], "truncated:", e["truncated"])
print("  U s  TI    Jdef   Jopt   dJ    | spd def opt d | travel def opt d (deg/s) | FAstd d | FAdel d | SSdel d | flap d | overspd def opt")
vr = []
for i, p in enumerate(e["pairs"]):
    d, o, c = p["default"], p["opt"], p["change_pct"]
    print("  %2d %d %5.1f %7.2f %7.2f %+6.1f | %.3f %.3f %+6.1f | %.3f %.3f %+6.1f | %+6.1f | %+6.1f | %+6.1f | %+6.1f | %.1f %.1f  (to %.0f s)" % (
        p["U"], p["seed"], p["TI_pct"], d[K[0]] / 1e3, o[K[0]] / 1e3, c[K[0]], d[K[1]], o[K[1]], c[K[1]], d[K[2]], o[K[2]], c[K[2]],
        c[K[3]], c[K[4]], c[K[5]], c[K[6]], d[K[7]], o[K[7]], p["t_end_s"]))
    vr.append([i + 1, p["U"], p["seed"], c[K[0]], c[K[1]], c[K[2]], c[K[3]], c[K[4]], c[K[6]]])
wcsv("valpairs.csv", ["i", "U", "seed", "dJ", "dspd", "dtravel", "dfa", "dfadel", "dflap"], vr)
for name, k in (("J", K[0]), ("speed", K[1]), ("travel", K[2]), ("FAstd", K[3]), ("FAdel", K[4]), ("SSdel", K[5]), ("flapDEL", K[6])):
    v = np.array([p["change_pct"][k] for p in e["pairs"]])
    print(f"  {name:8s} mean {v.mean():+6.1f}  median {np.median(v):+6.1f}  min {v.min():+6.1f}  max {v.max():+6.1f}  n<0: {(v < 0).sum()}/{len(v)}")
for u, v in e["by_U"].items():
    print(f"  U={u} n={v['n']} TI {v['TI_pct_mean']:.1f}: " + "  ".join(f"{k.split('_')[0]}_{k.split('_')[1]} {v['change_pct_mean'][k]:+.1f}" for k in K[:7]))
for p in e["pairs"]:
    out = []
    for c in ("default", "opt"):
        d = read_outb(os.path.join(RUNS, f"val_U{p['U']}_s{p['seed']}_{c}", OUTB))
        t = d["Time"]; w = (t >= 100) & (t <= p["t_end_s"])
        pr = np.abs(np.diff(d["BldPitch1"]) / np.diff(t))[w[1:]]
        out.append(f"{c}: max rate {pr.max():.2f} deg/s, at limit {100 * np.mean(pr >= 1.96):.2f}%, speed [{d['RotSpeed'][w].min():.2f},{d['RotSpeed'][w].max():.2f}], wind [{d['Wind1VelX'][w].min():.1f},{d['Wind1VelX'][w].max():.1f}]")
    print(f"  U{p['U']} s{p['seed']}  " + " | ".join(out))
# U14 seed 3 without the lull (500-550 s)
for c in ("default", "opt"):
    d = read_outb(os.path.join(RUNS, f"val_U14_s3_{c}", OUTB))
    t = d["Time"]; w = (t >= 100) & (t <= 644) & ~((t >= 500) & (t < 550))
    print(f"  U14 s3 {c}: J without 500-550 s = {np.mean((d['GenPwr'][w] - 22000.0) ** 2) / 1e3:.2f}")
# low-passed objective (< 0.5 Hz) for each pair: is the advantage in the controllable band?
bands = S.get("bands_hz")
print("  bands:", bands)
for p in e["pairs"]:
    md = json.load(open(os.path.join(RUNS, f"val_U{p['U']}_s{p['seed']}_default", "metrics.json")))
    mo = json.load(open(os.path.join(RUNS, f"val_U{p['U']}_s{p['seed']}_opt", "metrics.json")))
    if "band_var_power_kW2" in md and "band_var_power_kW2" in mo:
        bd, bo_ = np.array(md["band_var_power_kW2"]), np.array(mo["band_var_power_kW2"])
        print(f"  U{p['U']} s{p['seed']} power band var (1e3) default {np.round(bd / 1e3, 2).tolist()} opt {np.round(bo_ / 1e3, 2).tolist()}")

# ---------------------------------------------------------------- E3
r = S["E3_random"]
print("\nE3 n_random", r["n_random"], "BO best", r["bo_best"], "random best", r["random_best"], "at", r["random_best_omega"])
print("  BO best so far    ", np.round(r["bo_best_so_far"], 2).tolist())
print("  random best so far", np.round(r["random_best_so_far"], 2).tolist())
print("  mean J evals 6-20: BO", r["bo_mean_J_evals_6_20"], "random", r["random_mean_J_evals_6_20"])
bo = [ref_metrics(f"eval_{i:03d}") for i in range(1, 21)]
rnd = bo[:5] + [json.load(open(os.path.join(RUNS, f"rand_{i:03d}", "metrics.json"))) for i in range(6, 21)]
for name, k in (("J", "J_power_mse_kW2"), ("speed RMSE", "genspd_rmse_rpm")):
    a = np.array([m[k] for m in bo]); b = np.array([m[k] for m in rnd])
    print(f"  {name}: BO min {a.min():.4g} median(6-20) {np.median(a[5:]):.4g} | random min {b.min():.4g} median(6-20) {np.median(b[5:]):.4g}")
    print(f"     n of evals 6-20 below the best of the 5 initial ({a[:5].min():.4g}): BO {(a[5:] < a[:5].min()).sum()}, random {(b[5:] < b[:5].min()).sum()}")
print("  random 6-20 omega2:", [round(m["omega_pc"][1], 3) for m in rnd[5:]])
print("  random 6-20 J:", [round(m["J_power_mse_kW2"] / 1e3, 2) for m in rnd[5:]])
print("  BO 6-20 omega2 >= 0.175:", sum(m["omega_pc"][1] >= 0.175 for m in bo[5:]), " random:", sum(m["omega_pc"][1] >= 0.175 for m in rnd[5:]))
jb = np.array([m["J_power_mse_kW2"] for m in bo]) / 1e3; jr = np.array([m["J_power_mse_kW2"] for m in rnd]) / 1e3
wcsv("randbo.csv", ["k", "Jbo", "bestbo", "Jrand", "bestrand"],
     [[k + 1, jb[k], np.minimum.accumulate(jb)[k], jr[k], np.minimum.accumulate(jr)[k]] for k in range(20)])
allm = bo + rnd[5:]
w2 = np.array([m["omega_pc"][1] for m in allm]); J = np.array([m["J_power_mse_kW2"] for m in allm]); sp = np.array([m["genspd_rmse_rpm"] for m in allm])
print("  35 points: corr(J, w2) %.2f, corr(speed RMSE, w2) %.2f" % (np.corrcoef(J, w2)[0, 1], np.corrcoef(sp, w2)[0, 1]))
t = S["tradeoff_all_points"]
print("  trade-off: n points", t["n_points"], "pareto:", [(p["tag"], round(p["twr_fa_std_MNm"], 2), round(p["J_1e3kW2"], 2)) for p in t["pareto"]])
