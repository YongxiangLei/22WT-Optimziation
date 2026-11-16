"""
Supplementary analyses that need no new simulation: they re-use the 21 simulations of the finished
BO campaign (baseline + 20 candidates, 100-300 s window).

  A  split-half and block reliability of the objective ranking
  B  ranking versus averaging-window length
  C  alternative objectives and the regulation / load trade-off (non-dominated set, constrained choice)
  D  Gaussian-process surrogate (ARD Matern-5/2, numpy): leave-one-out accuracy and sensitivity indices
  E  reproducibility of the low-, mid- and high-frequency parts of the objective

Writes outputs/posthoc_summary.json, posthoc_candidates.csv and outputs/data/*.csv (read by the pgfplots figures)
"""
import csv
import json
import os

import numpy as np

from supp_common import SRC_RUNS, OUT, OUTB, P_REF, RATED_RPM, read_outb, ref_metrics, write_csv

TAGS = [f"eval_{i:03d}" for i in range(1, 21)]
BOUNDS = np.array([[0.1, 0.2], [0.1, 0.2], [0.1, 0.5]])


def rank(x):
    return np.argsort(np.argsort(x)).astype(float)


def corr(a, b):
    a = np.asarray(a, float) - np.mean(a); b = np.asarray(b, float) - np.mean(b)
    return float(np.sum(a * b) / np.sqrt(np.sum(a * a) * np.sum(b * b)))


def spearman(a, b):
    return corr(rank(np.asarray(a)), rank(np.asarray(b)))


# ----------------------------------------------------------------------------- GP (numpy only)
def matern52(X1, X2, ls):
    d = np.sqrt(np.maximum(((X1[:, None, :] - X2[None, :, :]) / ls) ** 2, 0).sum(-1))
    s = np.sqrt(5.0) * d
    return (1.0 + s + s ** 2 / 3.0) * np.exp(-s)


def gp_nll(X, y, ls, noise):
    K = matern52(X, X, ls) + (noise + 1e-8) * np.eye(len(y))
    L = np.linalg.cholesky(K)
    a = np.linalg.solve(L.T, np.linalg.solve(L, y))
    s2 = float(y @ a) / len(y)                       # profiled signal variance
    return 0.5 * len(y) * np.log(s2) + np.sum(np.log(np.diag(L))), s2


def gp_fit(X, y, seed=0):
    """Maximum marginal likelihood by random multistart + coordinate refinement on log-parameters."""
    rng = np.random.RandomState(seed)
    best = (np.inf, None)
    for _ in range(400):
        p = np.concatenate((rng.uniform(np.log(0.05), np.log(10.0), X.shape[1]), [rng.uniform(np.log(1e-4), np.log(1.0))]))
        try:
            v = gp_nll(X, y, np.exp(p[:-1]), np.exp(p[-1]))[0]
        except np.linalg.LinAlgError:
            continue
        if v < best[0]:
            best = (v, p)
    v, p = best
    step = 0.5
    while step > 1e-3:
        improved = False
        for i in range(len(p)):
            for sgn in (+1, -1):
                q = p.copy(); q[i] += sgn * step
                q[:-1] = np.clip(q[:-1], np.log(0.02), np.log(50.0)); q[-1] = np.clip(q[-1], np.log(1e-6), np.log(2.0))
                try:
                    vq = gp_nll(X, y, np.exp(q[:-1]), np.exp(q[-1]))[0]
                except np.linalg.LinAlgError:
                    continue
                if vq < v - 1e-10:
                    v, p, improved = vq, q, True
        if not improved:
            step *= 0.5
    return np.exp(p[:-1]), float(np.exp(p[-1])), float(v)


def gp_predict(X, y, ls, noise, Xs):
    K = matern52(X, X, ls) + (noise + 1e-8) * np.eye(len(y))
    return matern52(Xs, X, ls) @ np.linalg.solve(K, y)


def gp_loo(X, y, ls, noise):
    Kinv = np.linalg.inv(matern52(X, X, ls) + (noise + 1e-8) * np.eye(len(y)))
    return y - (Kinv @ y) / np.diag(Kinv)


def main():
    os.makedirs(OUT, exist_ok=True)
    base = ref_metrics("baseline")
    ev = [ref_metrics(t) for t in TAGS]
    W = np.array([m["omega_pc"] for m in ev])
    J = np.array([m["J_power_mse_kW2"] for m in ev])
    out = {"n_candidates": len(ev)}

    # time series (power error, speed error) for window studies
    series = {}
    for t in ["baseline"] + TAGS:
        d = read_outb(os.path.join(SRC_RUNS, t, OUTB))
        tt = d["Time"]; w = (tt >= 100.0) & (tt <= 300.0)
        series[t] = (tt[w], d["GenPwr"][w] - P_REF, d["GenSpeed"][w] - RATED_RPM)

    def jwin(t, a, b, k=1):
        tt, e, s = series[t]
        m = (tt >= a) & (tt <= b)
        return float(np.mean((e if k == 1 else s)[m] ** 2))

    # ---------------- A: split-half and block reliability
    h1 = np.array([jwin(t, 100, 200) for t in TAGS]); h2 = np.array([jwin(t, 200, 300) for t in TAGS])
    blocks = np.array([[jwin(t, a, a + 50) for a in (100, 150, 200, 250)] for t in TAGS])
    bb = np.array([jwin("baseline", a, a + 50) for a in (100, 150, 200, 250)])
    order = np.argsort(J)
    out["A_reliability"] = {
        "split_half_spearman_J": spearman(h1, h2), "split_half_pearson_J": corr(h1, h2),
        "split_half_spearman_speed": spearman([jwin(t, 100, 200, 2) for t in TAGS], [jwin(t, 200, 300, 2) for t in TAGS]),
        "half_vs_full_spearman": [spearman(h1, J), spearman(h2, J)],
        "block_spearman_matrix": [[spearman(blocks[:, i], blocks[:, j]) for j in range(4)] for i in range(4)],
        "block_vs_full_spearman": [spearman(blocks[:, i], J) for i in range(4)],
        "best_candidate": TAGS[int(order[0])],
        "best_candidate_rank_in_halves": [int(rank(h1)[order[0]]) + 1, int(rank(h2)[order[0]]) + 1],
        "best_candidate_rank_in_blocks": [int(rank(blocks[:, i])[order[0]]) + 1 for i in range(4)],
        "best_of_first_half": TAGS[int(np.argmin(h1))], "best_of_second_half": TAGS[int(np.argmin(h2))],
        "n_better_than_baseline_per_block": [int(np.sum(blocks[:, i] < bb[i])) for i in range(4)],
        "n_better_than_baseline_in_all_blocks": int(np.sum(np.all(blocks < bb[None, :], axis=1))),
        "top5_change_vs_baseline_pct_per_block": {TAGS[i]: [float(100 * (blocks[i, k] - bb[k]) / bb[k]) for k in range(4)] for i in order[:5]},
        "half_change_vs_baseline_pct_best": [float(100 * (h1[order[0]] / jwin("baseline", 100, 200) - 1)),
                                             float(100 * (h2[order[0]] / jwin("baseline", 200, 300) - 1))],
    }

    # ---------------- B: ranking versus window length
    Ts = [0.1, 0.5, 1, 2, 5, 10, 20, 50, 100, 150, 200]
    sp_lead = [spearman([jwin(t, 100, 100 + T) for t in TAGS], J) for T in Ts]
    sp_term = [spearman([jwin(t, 300 - T, 300) for t in TAGS], J) for T in Ts]
    # windows of length T placed at 8 start times: mean and min rank correlation with the full objective
    sp_mean, sp_min = [], []
    for T in Ts:
        starts = np.linspace(100, 300 - T, 8) if T < 200 else [100.0]
        v = [spearman([jwin(t, a, a + T) for t in TAGS], J) for a in starts]
        sp_mean.append(float(np.mean(v))); sp_min.append(float(np.min(v)))
    out["B_window"] = {"T_s": Ts, "spearman_leading_window": sp_lead, "spearman_terminal_window": sp_term,
                       "spearman_mean_over_8_positions": sp_mean, "spearman_min_over_8_positions": sp_min}

    write_csv("window.csv", ["T", "mean", "min", "term"], [[T, m, n, q] for T, m, n, q in zip(Ts, sp_mean, sp_min, sp_term)])
    write_csv("halves.csv", ["J1", "J2"], [[a / 1e3, b / 1e3] for a, b in zip(h1, h2)])

    # ---------------- C: alternative objectives and trade-off
    def col(k):
        return np.array([m[k] for m in ev])
    spd = col("genspd_rmse_rpm") ** 2
    fa = col("twr_fa_std_kNm"); travel = col("pitch_travel_deg")
    fa_band = np.array([m["band_var_twr_fa_kNm2"][1] for m in ev])           # 0.05-0.2 Hz
    out["C_objectives"] = {
        "spearman_J_vs_speed_mse": spearman(J, spd), "pearson_J_vs_speed_mse": corr(J, spd),
        "spearman_J_vs_twr_fa_std": spearman(J, fa), "spearman_J_vs_pitch_travel": spearman(J, travel),
        "spearman_J_vs_twr_fa_del": spearman(J, col("twr_fa_del_kNm")), "spearman_J_vs_flap_del": spearman(J, col("bld_flap_del_kNm")),
        "best_by_power": TAGS[int(np.argmin(J))], "best_by_speed": TAGS[int(np.argmin(spd))],
        "coefficient_of_variation_pct": {"J": float(100 * np.std(J) / np.mean(J)), "speed_mse": float(100 * np.std(spd) / np.mean(spd))},
        "range_ratio_max_over_min": {"J": float(J.max() / J.min()), "speed_mse": float(spd.max() / spd.min())},
    }
    j0, fa0, tr0 = base["J_power_mse_kW2"], base["twr_fa_std_kNm"], base["pitch_travel_deg"]
    nd = [i for i in range(len(ev)) if not any((fa[k] <= fa[i]) and (J[k] <= J[i]) and ((fa[k] < fa[i]) or (J[k] < J[i])) for k in range(len(ev)))]
    nd.sort(key=lambda i: fa[i])
    cons = {}
    for lim in (1, 2, 5, 10, 100):
        ok = [i for i in range(len(ev)) if 100 * (fa[i] / fa0 - 1) <= lim]
        if ok:
            i = min(ok, key=lambda k: J[k])
            cons[f"tower_fa_std_increase_le_{lim}pct"] = {"tag": TAGS[i], "omega_pc": W[i].tolist(), "J_change_pct": float(100 * (J[i] / j0 - 1)),
                                                           "twr_fa_std_change_pct": float(100 * (fa[i] / fa0 - 1)),
                                                           "pitch_travel_change_pct": float(100 * (travel[i] / tr0 - 1)),
                                                           "speed_rmse_change_pct": float(100 * (ev[i]["genspd_rmse_rpm"] / base["genspd_rmse_rpm"] - 1))}
    weighted = {}
    for lam in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0):
        c = J / j0 + lam * (fa / fa0) ** 2
        i = int(np.argmin(c))
        weighted[f"lambda_{lam}"] = {"tag": TAGS[i], "omega_pc": W[i].tolist(), "J_change_pct": float(100 * (J[i] / j0 - 1)),
                                     "twr_fa_var_change_pct": float(100 * ((fa[i] / fa0) ** 2 - 1)),
                                     "baseline_cost": 1.0 + lam, "cost": float(c[i])}
    out["C_tradeoff"] = {"non_dominated_J_vs_towerFA": [{"tag": TAGS[i], "omega_pc": W[i].tolist(), "J_change_pct": float(100 * (J[i] / j0 - 1)),
                                                         "twr_fa_std_change_pct": float(100 * (fa[i] / fa0 - 1)),
                                                         "pitch_travel_change_pct": float(100 * (travel[i] / tr0 - 1))} for i in nd],
                         "baseline_dominated_by": [TAGS[i] for i in range(len(ev)) if J[i] <= j0 and fa[i] <= fa0],
                         "constrained_choice": cons, "weighted_choice": weighted,
                         "pearson_omega2_vs_twr_fa_band_0p05_0p2": corr(W[:, 1], fa_band),
                         "linear_fit_dJ_pct_per_dFAstd_pct": float(np.polyfit(100 * (fa / fa0 - 1), 100 * (J / j0 - 1), 1)[0])}

    write_csv("tradeoff.csv", ["fa", "travel", "J", "w2"], [[fa[i] / 1e3, travel[i], J[i] / 1e3, W[i, 1]] for i in range(len(ev))])
    write_csv("tradeoff_nd.csv", ["fa", "J"], [[fa[i] / 1e3, J[i] / 1e3] for i in nd])

    # ---------------- D: GP surrogate
    X = (W - BOUNDS[:, 0]) / (BOUNDS[:, 1] - BOUNDS[:, 0])
    gp = {}
    for name, yraw in (("J", J), ("speed_mse", spd), ("twr_fa_std", fa)):
        y = (yraw - yraw.mean()) / yraw.std()
        ls, noise, nll = gp_fit(X, y)
        loo = gp_loo(X, y, ls, noise)
        rng = np.random.RandomState(1)
        n = 4000
        A = rng.uniform(size=(n, 3)); B = rng.uniform(size=(n, 3))
        fA = gp_predict(X, y, ls, noise, A); fB = gp_predict(X, y, ls, noise, B)
        var = np.var(np.concatenate((fA, fB)))
        S1, ST = [], []
        for i in range(3):
            AB = A.copy(); AB[:, i] = B[:, i]
            fAB = gp_predict(X, y, ls, noise, AB)
            S1.append(float(np.mean(fB * (fAB - fA)) / var))                 # Saltelli first-order estimator
            ST.append(float(0.5 * np.mean((fA - fAB) ** 2) / var))           # Jansen total-effect estimator
        grid = np.stack(np.meshgrid(*[np.linspace(0, 1, 21)] * 3, indexing="ij"), -1).reshape(-1, 3)
        fg = gp_predict(X, y, ls, noise, grid)
        xmin = grid[int(np.argmin(fg))] * (BOUNDS[:, 1] - BOUNDS[:, 0]) + BOUNDS[:, 0]
        gp[name] = {"length_scales_normalised": ls.tolist(), "noise_variance_fraction": noise,
                    "loo_r2": float(1 - np.sum((y - loo) ** 2) / np.sum(y ** 2)),
                    "loo_rmse_in_std_units": float(np.sqrt(np.mean((y - loo) ** 2))),
                    "loo_spearman": spearman(loo, y),
                    "sobol_first_order": S1, "sobol_total": ST,
                    "surrogate_minimiser_omega_pc": xmin.tolist(),
                    "surrogate_min_value": float(fg.min() * yraw.std() + yraw.mean())}
    out["D_gp_surrogate"] = gp

    # ---------------- E: which part of the objective is reproducible?
    full_series = {}
    for t in ["baseline"] + TAGS:
        d = read_outb(os.path.join(SRC_RUNS, t, OUTB))
        tt = d["Time"]; w = (tt >= 100.0) & (tt <= 300.0)
        full_series[t] = (tt[w], d["GenPwr"][w], d["TwrBsMyt"][w], d["BldPitch1"][w])

    def part(t, a, b, kind):
        tt, p, fa_, pit = full_series[t]
        m = (tt >= a) & (tt <= b)
        if kind == "fa":
            return float(np.std(fa_[m]))
        if kind == "travel":
            return float(np.sum(np.abs(np.diff(pit[m]))))
        x = p[m] - np.mean(p[m]); n = len(x)
        P = 2.0 * np.abs(np.fft.rfft(x)) ** 2 / n ** 2
        f = np.fft.rfftfreq(n, 0.01)
        lo_, hi_ = {"low": (1e-9, 0.05), "mid": (0.05, 0.5), "high": (0.5, 1e9)}[kind]
        return float(P[(f >= lo_) & (f < hi_)].sum())

    e = {"band_edges_hz": {"low": [0, 0.05], "mid": [0.05, 0.5], "high": [0.5, 50]}, "parts": {}, "blocks": []}
    for kind in ("low", "mid", "high", "fa", "travel"):
        a1 = np.array([part(t, 100, 200, kind) for t in TAGS]); a2 = np.array([part(t, 200, 300, kind) for t in TAGS])
        fu = np.array([part(t, 100, 300, kind) for t in TAGS])
        e["parts"][kind] = {"split_half_spearman": spearman(a1, a2), "split_half_pearson": corr(a1, a2),
                            "full_mean": float(fu.mean()), "full_min": float(fu.min()), "full_max": float(fu.max()),
                            "full_cv_pct": float(100 * fu.std() / fu.mean()), "baseline_full": part("baseline", 100, 300, kind),
                            "pearson_with_omega_full": [corr(W[:, k], fu) for k in range(3)],
                            "pearson_with_omega_first_half": [corr(W[:, k], a1) for k in range(3)],
                            "pearson_with_omega_second_half": [corr(W[:, k], a2) for k in range(3)],
                            "pearson_with_J_full": corr(fu, J)}
    e["pearson_J_with_omega_by_half"] = {"first": [corr(W[:, k], h1) for k in range(3)], "second": [corr(W[:, k], h2) for k in range(3)]}
    e["n_better_than_baseline_by_half"] = [int(np.sum(h1 < jwin("baseline", 100, 200))), int(np.sum(h2 < jwin("baseline", 200, 300)))]
    best_tag = TAGS[int(order[0])]
    for a in (100, 150, 200, 250):
        e["blocks"].append({"t": [a, a + 50],
                            "baseline_low_mid_high": [part("baseline", a, a + 50, k) for k in ("low", "mid", "high")],
                            "best_low_mid_high": [part(best_tag, a, a + 50, k) for k in ("low", "mid", "high")],
                            "pearson_J_block_with_omega": [corr(W[:, k], blocks[:, (a - 100) // 50]) for k in range(3)]})
    out["E_reproducible_parts"] = e
    write_csv("blocks.csv", ["block", "blow", "bmid", "bhigh", "olow", "omid", "ohigh"],
              [[i + 1] + [x / 1e3 for x in bl["baseline_low_mid_high"]] + [x / 1e3 for x in bl["best_low_mid_high"]] for i, bl in enumerate(e["blocks"])])

    # ---------------- F: paired moving-block bootstrap of the improvement (default vs best candidate)
    def lowpass(x, fc, dt=0.01):
        Xf = np.fft.rfft(x); fr = np.fft.rfftfreq(len(x), dt)
        Xf[fr >= fc] = 0.0
        return np.fft.irfft(Xf, n=len(x))

    pb, px = series["baseline"][1], series[best_tag][1]
    sb, sx = series["baseline"][2], series[best_tag][2]
    n = min(len(pb), len(px))
    pairs = {"J_power": (pb[:n] ** 2, px[:n] ** 2),
             "J_power_lowpass_0p5Hz": (lowpass(pb[:n], 0.5) ** 2, lowpass(px[:n], 0.5) ** 2),
             "speed_mse": (sb[:n] ** 2, sx[:n] ** 2)}
    boot = {"n_resamples": 5000, "method": "paired circular moving-block bootstrap of the squared-error series, 100-300 s", "results": {}}
    rng = np.random.RandomState(7)
    for name, (eb_, ex_) in pairs.items():
        boot["results"][name] = {"point_change_pct": float(100.0 * (ex_.mean() / eb_.mean() - 1.0))}
        for L_s in (10.0, 20.0, 40.0):
            L = int(round(L_s / 0.01)); nb = int(np.ceil(n / L))
            cb = np.concatenate(([0.0], np.cumsum(np.concatenate((eb_, eb_[:L])))))      # circular prefix sums
            cx = np.concatenate(([0.0], np.cumsum(np.concatenate((ex_, ex_[:L])))))
            starts = rng.randint(0, n, size=(boot["n_resamples"], nb))
            r = 100.0 * ((cx[starts + L] - cx[starts]).sum(axis=1) / (cb[starts + L] - cb[starts]).sum(axis=1) - 1.0)
            boot["results"][name][f"block_{int(L_s)}s"] = {"ci95_pct": [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))],
                                                          "se_pct": float(np.std(r)), "p_improvement": float(np.mean(r < 0))}
    out["F_bootstrap"] = boot

    # ---------------- G: origin of the ~1 Hz power oscillation (default-controller run)
    d = read_outb(os.path.join(SRC_RUNS, "baseline", OUTB))
    tt = d["Time"]; w = (tt >= 100.0) & (tt <= 300.0)
    nn = int(w.sum()); fq = np.fft.rfftfreq(nn, 0.01)
    band = (fq >= 0.8) & (fq <= 1.3)
    g = {"band_hz": [0.8, 1.3], "channels": {}}
    SP = {}
    for ch in ("GenPwr", "GenSpeed", "GenTq", "RotTorq", "RotThrust", "B1RootMxr", "B2RootMxr", "B3RootMxr", "B1RootMyr",
               "B1TipTDyr", "B2TipTDyr", "B3TipTDyr", "B1TipTDxr", "TwrBsMxt", "TwrBsMyt", "YawBrTDxt", "YawBrTDyt", "BldPitch1", "Wind1VelX"):
        if ch not in d:
            continue
        x = d[ch][w] - np.mean(d[ch][w])
        SP[ch] = 2.0 * np.abs(np.fft.rfft(x)) ** 2 / nn ** 2
        g["channels"][ch] = {"peak_hz_in_band": float(fq[band][np.argmax(SP[ch][band])]),
                             "band_share_of_variance_pct": float(100 * SP[ch][band].sum() / np.var(x)),
                             "band_std": float(np.sqrt(SP[ch][band].sum()))}

    def cross(a, b):
        """Band-averaged coherence and phase (deg) of b relative to a in 0.8-1.3 Hz (8 Hann segments)."""
        xa = d[a][w] - np.mean(d[a][w]); xb = d[b][w] - np.mean(d[b][w])
        seg = nn // 8
        Saa = Sbb = 0.0; Sab = 0.0 + 0.0j
        for k in range(8):
            A = np.fft.rfft(xa[k * seg:(k + 1) * seg] * np.hanning(seg)); B = np.fft.rfft(xb[k * seg:(k + 1) * seg] * np.hanning(seg))
            fs = np.fft.rfftfreq(seg, 0.01); m = (fs >= 0.8) & (fs <= 1.3)
            Saa += np.sum(np.abs(A[m]) ** 2); Sbb += np.sum(np.abs(B[m]) ** 2); Sab += np.sum(np.conj(A[m]) * B[m])
        return {"coherence": float(np.abs(Sab) ** 2 / (Saa * Sbb)), "phase_deg": float(np.degrees(np.angle(Sab)))}

    g["blade_edgewise_root_moment_phase"] = {"B1_B2": cross("B1RootMxr", "B2RootMxr"), "B1_B3": cross("B1RootMxr", "B3RootMxr")}
    g["blade_tip_inplane_phase"] = {"B1_B2": cross("B1TipTDyr", "B2TipTDyr"), "B1_B3": cross("B1TipTDyr", "B3TipTDyr")}
    g["genspeed_vs"] = {ch: cross("GenSpeed", ch) for ch in ("GenPwr", "B1RootMxr", "B1TipTDyr", "RotTorq", "TwrBsMxt", "YawBrTDyt", "GenTq") if ch in d}
    m1, m2, m3 = (d[c][w] - np.mean(d[c][w]) for c in ("B1RootMxr", "B2RootMxr", "B3RootMxr"))
    Pc = 2.0 * np.abs(np.fft.rfft((m1 + m2 + m3) / 3.0)) ** 2 / nn ** 2
    g["collective_share_of_B1_edgewise_band_variance_pct"] = float(100 * Pc[band].sum() / SP["B1RootMxr"][band].sum())
    g["collective_edgewise_peak_hz"] = float(fq[band][np.argmax(Pc[band])])
    blk = []
    for a in (100, 150, 200, 250):                   # does the frequency follow the rotor speed?
        mm = (tt >= a) & (tt < a + 50)
        x = d["GenPwr"][mm] - np.mean(d["GenPwr"][mm]); xp = np.zeros(8 * len(x)); xp[:len(x)] = x * np.hanning(len(x))
        fz = np.fft.rfftfreq(len(xp), 0.01); Pz = np.abs(np.fft.rfft(xp)) ** 2; bz = (fz >= 0.8) & (fz <= 1.3)
        rpm = float(np.mean(d["GenSpeed"][mm]))
        blk.append({"t": [a, a + 50], "peak_hz": float(fz[bz][np.argmax(Pz[bz])]), "mean_rpm": rpm,
                    "nine_P_hz": 9 * rpm / 60.0, "three_P_hz": 3 * rpm / 60.0})
    g["blocks"] = blk
    hb = fq >= 0.5                                   # dP/P = dOmega/Omega above the torque-loop bandwidth?
    g["above_0p5Hz"] = {"power_std_kW": float(np.sqrt(SP["GenPwr"][hb].sum())), "speed_std_rpm": float(np.sqrt(SP["GenSpeed"][hb].sum())),
                        "predicted_power_std_kW_from_speed": float(P_REF * np.sqrt(SP["GenSpeed"][hb].sum()) / RATED_RPM),
                        "torque_std_relative_pct": float(100 * np.sqrt(SP["GenTq"][hb].sum()) / np.mean(d["GenTq"][w])),
                        "speed_std_relative_pct": float(100 * np.sqrt(SP["GenSpeed"][hb].sum()) / RATED_RPM)}
    out["G_one_hz_origin"] = g


    with open(os.path.join(OUT, "posthoc_candidates.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tag", "omega1", "omega2", "omega3", "J_kW2", "J_100_200", "J_200_300", "speed_rmse_rpm", "pitch_travel_deg",
                    "twr_fa_std_kNm", "twr_fa_del_kNm", "twr_fa_var_0.05_0.2Hz", "twr_ss_std_kNm", "bld_flap_del_kNm"])
        for t, m, a, b in [("baseline", base, jwin("baseline", 100, 200), jwin("baseline", 200, 300))] + [(t, m, a, b) for t, m, a, b in zip(TAGS, ev, h1, h2)]:
            w.writerow([t, *[f"{x:.4f}" for x in m["omega_pc"]], f"{m['J_power_mse_kW2']:.1f}", f"{a:.1f}", f"{b:.1f}", f"{m['genspd_rmse_rpm']:.4f}",
                        f"{m['pitch_travel_deg']:.2f}", f"{m['twr_fa_std_kNm']:.0f}", f"{m['twr_fa_del_kNm']:.0f}", f"{m['band_var_twr_fa_kNm2'][1]:.4g}",
                        f"{m['twr_ss_std_kNm']:.0f}", f"{m.get('bld_flap_del_kNm', float('nan')):.0f}"])
    with open(os.path.join(OUT, "posthoc_summary.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
