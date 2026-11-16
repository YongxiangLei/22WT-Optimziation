"""Characterise the sweep runs (E1): where and how does the loop lose stability above omega_pc(18) = 0.24?"""
import glob
import json
import os
import numpy as np
from supp_common import RUNS, SRC_RUNS, OUTB, read_outb, read_text

RATED = 7.0611


def spec_peak(x, dt, fmin=0.01):
    x = x - x.mean()
    P = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), dt)
    k = f >= fmin
    return float(f[k][np.argmax(P[k])])


def band_share(x, dt, a, b):
    x = x - x.mean()
    P = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), dt)
    return float(P[(f >= a) & (f < b)].sum() / P[1:].sum())


def show(tag, path):
    d = read_outb(path)
    t = d["Time"]
    dt = t[1] - t[0]
    w = t >= 100
    rs, p, pit, tq = d["RotSpeed"][w], d["GenPwr"][w], d["BldPitch1"][w], d["GenTq"][w]
    pr = np.diff(d["BldPitch1"]) / dt
    prw = pr[t[1:] >= 100]
    lim = np.abs(prw).max()
    e = np.abs(d["RotSpeed"] - RATED)
    big = np.where((e > 0.6) & (t >= 20))[0]
    onset = f"{t[big[0]]:.0f} s" if len(big) else "never"
    halves = [float(np.std(d["RotSpeed"][(t >= a) & (t < a + 50)])) for a in range(100, 300, 50) if (t >= a + 49).any()]
    print(f"{tag:22s} end {t[-1]:5.1f}s  speed [{rs.min():.2f},{rs.max():.2f}] std {rs.std():.3f} rpm  f_peak(speed) {spec_peak(rs, dt):.3f} Hz"
          f"  f_peak(pitch) {spec_peak(pit, dt):.3f} Hz  share 0.02-0.08 Hz {band_share(rs, dt, 0.02, 0.08):.2f}"
          f"  P [{p.min() / 1e3:.2f},{p.max() / 1e3:.2f}] MW  Tq [{tq.min() / 1e3:.1f},{tq.max() / 1e3:.1f}] MNm"
          f"  pitch [{pit.min():.1f},{pit.max():.1f}] deg  max|rate| {lim:.2f} deg/s, time at >=0.98 max {np.mean(np.abs(prw) >= 0.98 * lim) * 100:.1f}%"
          f"  |err|>0.6 rpm first at {onset}  speed std per 50 s {['%.2f' % h for h in halves]}"
          f"  wind mean {d['Wind1VelX'][w].mean():.1f} [{d['Wind1VelX'][w].min():.1f},{d['Wind1VelX'][w].max():.1f}]")


show("eval_018 (0.200, I1)", os.path.join(SRC_RUNS, "sens_i1_eval_018", OUTB))
for path in sorted(glob.glob(os.path.join(RUNS, "sweep_w2_*", OUTB))):
    show(os.path.basename(os.path.dirname(path)), path)

# controller limits in DISCON
dis = glob.glob(os.path.join(RUNS, "sweep_w2_0.300", "*DISCON*"))[0]
for l in read_text(dis).splitlines():
    if any(k in l for k in ("PC_MaxRat", "PC_MinRat", "PC_MaxPit", "PC_MinPit", "VS_MaxTq", "VS_MaxRat", "PC_RefSpd", "VS_ControlMode", "VS_ConstPower", "PC_GS_angles", "PC_GS_KP", "PC_GS_KI", "F_LPFType", "F_LPFCornerFreq", "PS_Mode", "Fl_Mode", "TD_Mode", "TRA_Mode", "SD_Mode")):
        print(l[:170])
m = json.load(open(os.path.join(RUNS, "sweep_w2_0.300", "metrics.json")))
print({k: m[k] for k in ("genspd_max_rpm", "genspd_min_rpm", "overspeed_pct", "pitch_rate_max_degps", "power_maxdev_kW", "twr_fa_std_kNm", "twr_fa_del_kNm")})
