"""
Shared helpers for the supplementary experiments (numpy only; no scipy / sklearn / ROSCO toolbox,
because those DLLs are blocked by the application-control policy on this machine).

The pitch gain schedule is rebuilt from the linearised plant coefficients A(v), B(v), which are
recovered from an existing gain_schedule.json written by the ROSCO toolbox:
    Ki = omega^2 / B            ->  B = omega^2 / Ki
    Kp = (2 zeta omega + A) / B ->  A = Kp B - 2 zeta omega
omega(v) and zeta(v) follow from the toolbox's sigma interpolation between the breakpoints U_pc.
prepare.py checks this reconstruction against all existing evaluations before any run is prepared.
"""
import json
import os
import re

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = r"D:\experiment\rosco_rerun"                 # finished BO run (read-only)
SRC_RUNS = os.path.join(SRC, "runs")
RUNS = os.path.join(ROOT, "runs")
WIND = os.path.join(ROOT, "wind")
OUT = os.path.join(ROOT, "outputs")
SHARED = os.path.join(RUNS, "IEA-22-280-RWT")
ENV = os.environ.get("ROSCO_ENV", r"D:\software\micromamba\envs\rosco-env")
OPENFAST = os.path.join(ENV, "Library", "bin", "openfast.exe")
TURBSIM = os.path.join(ENV, "Library", "bin", "turbsim.exe")

FST = "IEA-22-280-RWT-Monopile.fst"
OUTB = FST.replace(".fst", ".outb")
DISCON = "IEA-22-280-RWT_DISCON.IN"
INFLOW = "IEA-22-280-RWT_InflowFile.dat"
TOP_FILES = [FST, "IEA-22-280-RWT-Monopile.yaml", "IEA-22-280-RWT_AeroDyn15.dat", "IEA-22-280-RWT_ElastoDyn.dat",
             "IEA-22-280-RWT_ElastoDyn_tower.dat", "IEA-22-280-RWT_HydroDyn.dat",
             "IEA-22-280-RWT_ServoDyn.dat", "IEA-22-280-RWT_SubDyn.dat"]

P_REF = 22000.0                                    # kW
RATED_RPM = 0.739436 * 60.0 / (2.0 * np.pi)        # direct drive
U_PC = [12.0, 18.0, 24.0]
ZETA_PC = [0.847280836303482, 1.756230134689656, 0.7443639812392495]
OMEGA_DEFAULT = [0.1039601890550169, 0.11266788743371176, 0.289233848967533]
OMEGA_BEST = [0.11317919544621384, 0.2, 0.3216420253369157]          # eval_018
T0 = 100.0                                         # start of every evaluation window [s]
BANDS = [(0.0, 0.05), (0.05, 0.2), (0.2, 0.5), (0.5, 2.0), (2.0, 50.0)]


# ----------------------------------------------------------------------------- file helpers
def set_param(path, key, value):
    """Replace the value (first token) of the FAST input line whose label is `key`."""
    with open(path, "r") as f:
        lines = f.readlines()
    n = 0
    for i, line in enumerate(lines):
        tok = line.split()
        if len(tok) >= 2 and tok[1] == key:
            m = re.match(r'^(\s*)("[^"]*"|\S+)(.*)$', line.rstrip("\n"))
            lines[i] = f"{m.group(1)}{value}{m.group(3)}\n"
            n += 1
    if n != 1:
        raise RuntimeError(f"{key}: found {n} lines in {path}")
    with open(path, "w") as f:
        f.writelines(lines)


def read_outb(path):
    with open(path, "rb") as f:
        fid = np.frombuffer(f.read(2), "<i2")[0]
        clen = 10
        if fid == 4:
            clen = int(np.frombuffer(f.read(2), "<i2")[0])
        nc, nt = np.frombuffer(f.read(8), "<i4")
        if fid == 1:
            tscl, toff = np.frombuffer(f.read(16), "<f8")
        else:
            t1, dtt = np.frombuffer(f.read(16), "<f8")
        scl = np.frombuffer(f.read(4 * nc), "<f4")
        off = np.frombuffer(f.read(4 * nc), "<f4")
        ld = int(np.frombuffer(f.read(4), "<i4")[0])
        f.read(ld)
        names = [f.read(clen).decode("ascii").strip() for _ in range(nc + 1)]
        f.read(clen * (nc + 1))
        if fid == 1:
            time_ = (np.frombuffer(f.read(4 * nt), "<i4") - toff) / tscl
        else:
            time_ = t1 + dtt * np.arange(nt)
        raw = np.frombuffer(f.read(2 * nc * nt), "<i2").reshape(nt, nc)
    data = (raw.astype(np.float64) - off) / scl
    out = {"Time": time_}
    for i, n in enumerate(names[1:]):
        out[n] = data[:, i]
    return out


def read_text(path):
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or raw[1:200:2].count(0) > 50:
        return raw.decode("utf-16", errors="ignore")
    return raw.decode("utf-8", errors="ignore")


# ----------------------------------------------------------------------------- gain schedule
def sigma(tt, t0, t1, y0=0.0, y1=1.0):
    """Cubic 'sigma' blend, same as rosco.toolbox.controller.sigma."""
    c = 1.0 / (t0 - t1) ** 3
    a3 = 2.0 * c
    a2 = -3.0 * (t0 + t1) * c
    a1 = 6.0 * t1 * t0 * c
    a0 = (t0 - 3.0 * t1) * t0 ** 2 * c
    tt = np.asarray(tt, float)
    ss = a3 * tt ** 3 + a2 * tt ** 2 + a1 * tt + a0
    return (y1 - y0) * ss + y0


def multi_sigma(xx, x_bp, y_bp):
    xx = np.asarray(xx, float)
    yy = np.zeros_like(xx)
    for i in range(len(x_bp) - 1):
        ind = (xx >= x_bp[i]) & (xx < x_bp[i + 1])
        yy[ind] = sigma(xx[ind], x_bp[i], x_bp[i + 1], y0=y_bp[i], y1=y_bp[i + 1])
    yy[xx < x_bp[0]] = y_bp[0]
    yy[xx >= x_bp[-1]] = y_bp[-1]
    return yy


class Plant:
    """A(v), B(v) recovered from the baseline gain schedule of the finished BO run."""

    def __init__(self):
        with open(os.path.join(SRC_RUNS, "baseline", "gain_schedule.json")) as f:
            g = json.load(f)
        self.v = np.array(g["v"])
        om, ze = np.array(g["omega_pc"]), np.array(g["zeta_pc"])
        kp, ki = np.array(g["Kp"]), np.array(g["Ki"])
        self.B = om ** 2 / ki
        self.A = kp * self.B - 2.0 * ze * om

    def schedule(self, omegas):
        om = multi_sigma(self.v, U_PC, list(omegas))
        ze = multi_sigma(self.v, U_PC, ZETA_PC)
        kp = (2.0 * ze * om + self.A) / self.B
        ki = om ** 2 / self.B
        return {"v": self.v.tolist(), "omega_pc": om.tolist(), "zeta_pc": ze.tolist(),
                "Kp": kp.tolist(), "Ki": ki.tolist()}


def write_discon(run_dir, sched):
    """Copy the baseline DISCON.IN and replace the PC_GS_KP / PC_GS_KI rows (the only rows that
    differ between evaluations of the finished BO run)."""
    with open(os.path.join(SRC_RUNS, "baseline", DISCON), "r") as f:
        lines = f.readlines()
    done = 0
    for i, line in enumerate(lines):
        for key, vals in (("PC_GS_KP", sched["Kp"]), ("PC_GS_KI", sched["Ki"])):
            if "!" in line and line.split("!", 1)[1].strip().startswith(key):
                lines[i] = "  ".join(f"{x:.6f}" for x in vals) + "                ! " + line.split("!", 1)[1]
                done += 1
    if done != 2:
        raise RuntimeError(f"DISCON rows replaced: {done}")
    with open(os.path.join(run_dir, DISCON), "w") as f:
        f.writelines(lines)


def read_discon_row(path, key):
    for line in open(path):
        if "!" in line and line.split("!", 1)[1].strip().startswith(key):
            return np.array([float(x) for x in line.split("!", 1)[0].split()])
    raise RuntimeError(key)


# ----------------------------------------------------------------------------- metrics
def turning_points(x):
    dx = np.diff(x)
    keep = np.concatenate(([True], dx[1:] * dx[:-1] < 0, [True]))
    x = x[keep]
    return x[np.concatenate(([True], np.diff(x) != 0))]


def rainflow(x):
    """ASTM E1049 three-point rainflow; returns (ranges, counts). Same routine as extra_analysis.py."""
    tp = turning_points(np.asarray(x, float))
    stack, ranges, counts = [], [], []
    for p in tp:
        stack.append(p)
        while len(stack) >= 3:
            r1 = abs(stack[-2] - stack[-3])
            r2 = abs(stack[-1] - stack[-2])
            if r2 < r1:
                break
            if len(stack) == 3:
                ranges.append(r1); counts.append(0.5)
                stack.pop(0)
            else:
                ranges.append(r1); counts.append(1.0)
                last = stack.pop(); stack.pop(); stack.pop(); stack.append(last)
    for i in range(len(stack) - 1):
        ranges.append(abs(stack[i + 1] - stack[i])); counts.append(0.5)
    return np.array(ranges), np.array(counts)


def del_1hz(x, duration, m):
    r, n = rainflow(x)
    return float((np.sum(n * r ** m) / duration) ** (1.0 / m))


def band_variance(x, dt):
    """One-sided periodogram without windowing; the band values sum to the variance."""
    x = np.asarray(x, float) - np.mean(x)
    n = len(x)
    P = 2.0 * np.abs(np.fft.rfft(x)) ** 2 / n ** 2
    P[0] = 0.0
    f = np.fft.rfftfreq(n, dt)
    return [float(P[(f >= a) & (f < b)].sum()) for a, b in BANDS]


def metrics(outb, t0=T0, t1=None):
    d = read_outb(outb)
    t = d["Time"]
    t1 = float(t[-1]) if t1 is None else t1
    w = (t >= t0) & (t <= t1)
    tt = t[w]
    dt = float(tt[1] - tt[0])
    dur = float(tt[-1] - tt[0])
    p, gs, pit = d["GenPwr"][w], d["GenSpeed"][w], d["BldPitch1"][w]
    pr = np.diff(pit) / np.diff(tt)
    u = d["Wind1VelX"][w]
    m = {
        "t_start_s": float(tt[0]), "t_end_s": float(tt[-1]), "sim_end_s": float(t[-1]),
        "J_power_mse_kW2": float(np.mean((p - P_REF) ** 2)),
        "power_rmse_kW": float(np.sqrt(np.mean((p - P_REF) ** 2))),
        "power_mean_kW": float(np.mean(p)), "power_std_kW": float(np.std(p)),
        "power_maxdev_kW": float(np.max(np.abs(p - P_REF))),
        "genspd_rmse_rpm": float(np.sqrt(np.mean((gs - RATED_RPM) ** 2))),
        "genspd_max_rpm": float(gs.max()), "genspd_min_rpm": float(gs.min()),
        "overspeed_pct": float(100.0 * (gs.max() / RATED_RPM - 1.0)),
        "pitch_mean_deg": float(np.mean(pit)), "pitch_std_deg": float(np.std(pit)),
        "pitch_travel_deg": float(np.sum(np.abs(np.diff(pit)))),
        "pitch_travel_degps": float(np.sum(np.abs(np.diff(pit))) / dur),
        "pitch_rate_rms_degps": float(np.sqrt(np.mean(pr ** 2))),
        "pitch_rate_max_degps": float(np.max(np.abs(pr))),
        "gentq_std_kNm": float(np.std(d["GenTq"][w])),
        "thrust_std_kN": float(np.std(d["RotThrust"][w])),
        "wind_mean_ms": float(np.mean(u)), "wind_std_ms": float(np.std(u)),
        "wind_min_ms": float(u.min()), "wind_max_ms": float(u.max()),
        "band_edges_hz": BANDS,
        "band_var_power_kW2": band_variance(p, dt),
        "band_var_pitch_deg2": band_variance(pit, dt),
        "band_var_genspd_rpm2": band_variance(gs, dt),
    }
    for ch, key, mm in (("TwrBsMyt", "twr_fa", 4), ("TwrBsMxt", "twr_ss", 4), ("B1RootMyr", "bld_flap", 10)):
        if ch in d:
            y = d[ch][w]
            m[f"{key}_std_kNm"] = float(np.std(y))
            m[f"{key}_del_kNm"] = del_1hz(y, dur, mm)
            m[f"{key}_max_kNm"] = float(np.max(np.abs(y)))
            m[f"band_var_{key}_kNm2"] = band_variance(y, dt)
    return m


# ----------------------------------------------------------------------------- reference runs
def ref_metrics(tag):
    """Metrics of a run of the finished BO campaign, recomputed with metrics() and cached."""
    cache = os.path.join(OUT, "ref_cache", tag + ".json")
    if os.path.exists(cache):
        return json.load(open(cache))
    m = metrics(os.path.join(SRC_RUNS, tag, OUTB))
    m["tag"] = tag
    m["omega_pc"] = json.load(open(os.path.join(SRC_RUNS, tag, "parameters.json")))["omega_pc"]
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w") as f:
        json.dump(m, f, indent=1)
    return m


def write_csv(name, header, rows):
    """Small data file for the pgfplots figures of the manuscript."""
    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    with open(os.path.join(OUT, "data", name), "w", newline="") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(f"{x:.6g}" if isinstance(x, (float, np.floating)) else str(x) for x in r) + "\n")
