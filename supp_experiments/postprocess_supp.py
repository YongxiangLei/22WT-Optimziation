"""
Post-processing of the supplementary simulations. Reads runs/*/metrics.json (and the finished BO run
for reference points); writes outputs/supp_results.csv, outputs/supp_summary.json and the data files
outputs/data/*.csv that the pgfplots figures of the manuscript read.

  python postprocess_supp.py

numpy only: the matplotlib rendering DLL is blocked by the application-control policy on this machine,
so the figures are drawn by LaTeX (pgfplots) from the CSV files. Missing or failed runs are skipped and
listed in supp_summary.json.
"""
import csv
import json
import os

import numpy as np

from supp_common import ROOT, RUNS, OUT, BANDS, ref_metrics, write_csv, read_outb, metrics

MIN_END = 400.0     # s; a validation run that stopped earlier than this is not used

KEYS = ["J_power_mse_kW2", "power_rmse_kW", "genspd_rmse_rpm", "overspeed_pct", "pitch_travel_degps",
        "pitch_rate_rms_degps", "pitch_rate_max_degps", "thrust_std_kN", "twr_fa_std_kNm", "twr_ss_std_kNm",
        "twr_fa_del_kNm", "twr_ss_del_kNm", "bld_flap_del_kNm", "wind_mean_ms", "wind_std_ms"]
VKEYS = ["J_power_mse_kW2", "power_rmse_kW", "genspd_rmse_rpm", "overspeed_pct", "pitch_travel_degps",
         "twr_fa_std_kNm", "twr_ss_std_kNm", "twr_fa_del_kNm", "twr_ss_del_kNm", "bld_flap_del_kNm", "thrust_std_kN"]


def load(tag):
    p = os.path.join(RUNS, tag, "metrics.json")
    if not os.path.exists(p):
        return None
    r = json.load(open(p))
    return r if r.get("status") == "OK" else None


def pct(a, b):
    return 100.0 * (b - a) / a


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = json.load(open(os.path.join(ROOT, "jobs.json")))
    res = {j["tag"]: load(j["tag"]) for j in jobs}
    missing = [t for t, r in res.items() if r is None]
    summary = {"n_jobs": len(jobs), "n_ok": len(jobs) - len(missing), "missing_or_failed": missing}

    with open(os.path.join(OUT, "supp_results.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tag", "group", "omega1", "omega2", "omega3", "U", "seed", "controller", "tmax", "wall_h"] + KEYS)
        for j in jobs:
            r = res[j["tag"]]
            if r is None:
                continue
            w.writerow([j["tag"], j["group"], *[f"{x:.4f}" for x in r["omega_pc"]], j.get("U", ""), j.get("seed", ""),
                        j.get("controller", ""), j["tmax"], f"{r['wall_s'] / 3600:.2f}"]
                       + [f"{r.get(k, float('nan')):.5g}" for k in KEYS])

    base = ref_metrics("sens_i1_baseline")          # InterpOrder = 1, same numerics as the new runs
    best = ref_metrics("sens_i1_eval_018")

    # ------------------------------------------------------------------ E1: sweep of omega_pc(18 m/s)
    sw = sorted([r for r in res.values() if r is not None and r["group"] == "E1_sweep"] + [best],
                key=lambda r: r["omega_pc"][1])
    if len(sw) > 1:
        rows = []
        for r in sw:
            rows.append({"omega2": r["omega_pc"][1], "J_1e3kW2": r["J_power_mse_kW2"] / 1e3,
                         "power_rmse_kW": r["power_rmse_kW"], "genspd_rmse_rpm": r["genspd_rmse_rpm"],
                         "pitch_travel_deg": r["pitch_travel_deg"], "pitch_rate_max_degps": r["pitch_rate_max_degps"],
                         "twr_fa_std_MNm": r["twr_fa_std_kNm"] / 1e3, "twr_fa_del_MNm": r["twr_fa_del_kNm"] / 1e3,
                         "twr_ss_std_MNm": r["twr_ss_std_kNm"] / 1e3,
                         "band_var_power_1e3kW2": [x / 1e3 for x in r["band_var_power_kW2"]],
                         "band_var_twr_fa_ratio_to_default": [x / y for x, y in zip(r["band_var_twr_fa_kNm2"], base["band_var_twr_fa_kNm2"])]})
        summary["E1_sweep"] = {"omega1_omega3": [sw[0]["omega_pc"][0], sw[0]["omega_pc"][2]], "rows": rows,
                               "default": {"J_1e3kW2": base["J_power_mse_kW2"] / 1e3, "pitch_travel_deg": base["pitch_travel_deg"],
                                           "twr_fa_std_MNm": base["twr_fa_std_kNm"] / 1e3, "genspd_rmse_rpm": base["genspd_rmse_rpm"]},
                               "argmin_J_omega2": float(min(sw, key=lambda r: r["J_power_mse_kW2"])["omega_pc"][1])}
        write_csv("sweep.csv", ["omega2", "J", "speed_rmse", "pitch_travel", "twr_fa_std", "twr_fa_del"],
                  [[x["omega2"], x["J_1e3kW2"], x["genspd_rmse_rpm"], x["pitch_travel_deg"], x["twr_fa_std_MNm"], x["twr_fa_del_MNm"]] for x in rows])

    # ------------------------------------------------------------------ E2: validation on unseen wind fields
    val = [r for r in res.values() if r is not None and r["group"] == "E2_validation"]
    pairs = {}
    for r in val:
        pairs.setdefault((r["U"], r["seed"]), {})[r["controller"]] = r
    e2 = {"pairs": [], "by_U": {}, "incomplete": [], "truncated": []}
    for u, s in sorted(set((j["U"], j["seed"]) for j in jobs if j["group"] == "E2_validation")):
        p = pairs.get((u, s), {})
        t_end = None
        if "default" not in p or "opt" not in p:
            # A run that stopped with a solver error late in the simulation is still used: both members of
            # the pair are then evaluated over the same shortened window (ending 5 s before the stop).
            outb = {c: os.path.join(RUNS, f"val_U{u}_s{s}_{c}", "IEA-22-280-RWT-Monopile.outb") for c in ("default", "opt")}
            ends = {c: (float(read_outb(f)["Time"][-1]) if os.path.exists(f) else 0.0) for c, f in outb.items()}
            started = all(os.path.exists(os.path.join(RUNS, f"val_U{u}_s{s}_{c}", "metrics.json")) for c in outb)
            if not started or min(ends.values()) < MIN_END:
                e2["incomplete"].append({"U": u, "seed": s, "sim_end_s": ends}); continue
            t_end = float(np.floor(min(ends.values()) - 5.0))
            p = {c: metrics(f, t1=t_end) for c, f in outb.items()}
            e2["truncated"].append({"U": u, "seed": s, "sim_end_s": ends, "evaluated_to_s": t_end})
        d, o = p["default"], p["opt"]
        e2["pairs"].append({"U": u, "seed": s, "wind_mean": d["wind_mean_ms"], "TI_pct": 100 * d["wind_std_ms"] / d["wind_mean_ms"],
                            "t_end_s": t_end if t_end is not None else d["t_end_s"],
                            "default": {k: d[k] for k in VKEYS}, "opt": {k: o[k] for k in VKEYS},
                            "change_pct": {k: pct(d[k], o[k]) for k in VKEYS}})
    for u in sorted(set(p["U"] for p in e2["pairs"])):
        ps = [p for p in e2["pairs"] if p["U"] == u]
        e2["by_U"][str(u)] = {"n": len(ps), "TI_pct_mean": float(np.mean([p["TI_pct"] for p in ps])),
                              "default_mean": {k: float(np.mean([p["default"][k] for p in ps])) for k in VKEYS},
                              "opt_mean": {k: float(np.mean([p["opt"][k] for p in ps])) for k in VKEYS},
                              "change_pct_mean": {k: float(np.mean([p["change_pct"][k] for p in ps])) for k in VKEYS},
                              "change_pct_min": {k: float(np.min([p["change_pct"][k] for p in ps])) for k in VKEYS},
                              "change_pct_max": {k: float(np.max([p["change_pct"][k] for p in ps])) for k in VKEYS}}
    if e2["pairs"]:
        e2["all"] = {"n": len(e2["pairs"]),
                     "change_pct_mean": {k: float(np.mean([p["change_pct"][k] for p in e2["pairs"]])) for k in VKEYS},
                     "n_improved": {k: int(sum(p["change_pct"][k] < 0 for p in e2["pairs"])) for k in VKEYS}}
        write_csv("validation_pairs.csv", ["U", "seed", "TI"] + VKEYS,
                  [[p["U"], p["seed"], p["TI_pct"]] + [p["change_pct"][k] for k in VKEYS] for p in e2["pairs"]])
        write_csv("validation_mean.csv", ["U", "n"] + VKEYS,
                  [[int(u), v["n"]] + [v["change_pct_mean"][k] for k in VKEYS] for u, v in e2["by_U"].items()])
    summary["E2_validation"] = e2

    # ------------------------------------------------------------------ E3: random search vs BO; trade-off cloud
    bo = [ref_metrics(f"eval_{i:03d}") for i in range(1, 21)]
    rnd = [bo[i] for i in range(5)] + [r for r in (res.get(f"rand_{i:03d}") for i in range(6, 21)) if r is not None]
    jb = np.array([r["J_power_mse_kW2"] for r in bo]) / 1e3
    jr = np.array([r["J_power_mse_kW2"] for r in rnd]) / 1e3
    summary["E3_random"] = {"n_random": len(rnd), "bo_best_so_far": np.minimum.accumulate(jb).tolist(),
                            "random_best_so_far": np.minimum.accumulate(jr).tolist(),
                            "bo_best": float(jb.min()), "random_best": float(jr.min()),
                            "random_best_omega": rnd[int(np.argmin(jr))]["omega_pc"],
                            "bo_mean_J_evals_6_20": float(jb[5:].mean()),
                            "random_mean_J_evals_6_20": float(jr[5:].mean()) if len(jr) > 5 else None}
    if len(rnd) == 20:
        write_csv("random_vs_bo.csv", ["k", "J_bo", "best_bo", "J_rand", "best_rand"],
                  [[k + 1, jb[k], np.minimum.accumulate(jb)[k], jr[k], np.minimum.accumulate(jr)[k]] for k in range(20)])

    cloud = bo + [r for r in res.values() if r is not None and r["group"] in ("E1_sweep", "E3_random")]
    x = np.array([r["twr_fa_std_kNm"] for r in cloud]) / 1e3
    y = np.array([r["J_power_mse_kW2"] for r in cloud]) / 1e3
    nd = [i for i in range(len(cloud)) if not any((x[k] <= x[i]) and (y[k] <= y[i]) and ((x[k] < x[i]) or (y[k] < y[i])) for k in range(len(cloud)))]
    nd.sort(key=lambda i: x[i])
    summary["tradeoff_all_points"] = {"n_points": len(cloud),
                                      "pareto": [{"tag": cloud[i].get("tag"), "omega_pc": cloud[i]["omega_pc"], "twr_fa_std_MNm": float(x[i]),
                                                  "J_1e3kW2": float(y[i]), "pitch_travel_deg": cloud[i]["pitch_travel_deg"]} for i in nd],
                                      "default": {"twr_fa_std_MNm": base["twr_fa_std_kNm"] / 1e3, "J_1e3kW2": base["J_power_mse_kW2"] / 1e3}}
    write_csv("tradeoff_all.csv", ["twr_fa_std", "pitch_travel", "J", "omega2"],
              [[x[i], cloud[i]["pitch_travel_deg"], y[i], cloud[i]["omega_pc"][1]] for i in range(len(cloud))])

    summary["bands_hz"] = BANDS
    with open(os.path.join(OUT, "supp_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({k: summary[k] for k in ("n_jobs", "n_ok", "missing_or_failed")}, indent=1))


if __name__ == "__main__":
    main()
