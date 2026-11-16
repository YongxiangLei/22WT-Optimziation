"""
Wind-speed and gain-schedule figures of the manuscript, redrawn in the style of the other figures
(same fonts, sizes and colours: default = blue, optimized = orange).

  fig_wind.pdf  - hub-height wind speed of the tuning realization, 100-300 s
  fig_gains.pdf - scheduled natural frequency, damping ratio and PI gains, default against optimized

  python fig_basic.py [preview_dir]
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from supp_common import SRC_RUNS, OUT, OUTB, read_outb

PAPER = r"D:\experiment\paper_ieee_draft\figures"
PREV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "preview")
os.makedirs(PREV, exist_ok=True)
C_BLUE, C_ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e1e0d9"
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "mathtext.fontset": "stix",
    "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
    "xtick.major.width": 0.5, "ytick.major.width": 0.5, "grid.color": GRID, "grid.linewidth": 0.5, "pdf.fonttype": 42,
})

# ---------------------------------------------------------------- wind
d = read_outb(os.path.join(SRC_RUNS, "baseline", OUTB))
w = (d["Time"] >= 100) & (d["Time"] <= 300)
t, u = d["Time"][w], d["Wind1VelX"][w]
mean, ti = float(u.mean()), float(u.std() / u.mean())
print(f"wind: mean {mean:.2f} m/s, std {u.std():.2f}, TI {100 * ti:.1f} %, range {u.min():.1f}-{u.max():.1f}")
fig, ax = plt.subplots(figsize=(3.5, 1.75))
ax.plot(t[::2], u[::2], color=MUTED, linewidth=0.6)
ax.axhline(mean, color=INK, linewidth=0.8, linestyle=(0, (4, 2)))
ax.text(190, 22.6, f"Mean {mean:.1f} m/s (dashed), turbulence intensity {100 * ti:.1f}%", fontsize=7, color=INK, va="center", ha="center")
ax.set_xlim(100, 300); ax.set_ylim(14, 23.5)
ax.set_xlabel("Time (s)"); ax.set_ylabel("Wind speed (m/s)")
ax.grid(True)
fig.subplots_adjust(left=0.125, right=0.98, top=0.97, bottom=0.215)
fig.savefig(os.path.join(PAPER, "fig_wind.pdf"))
fig.savefig(os.path.join(PREV, "fig_wind.png"), dpi=220)
plt.close(fig)

# ---------------------------------------------------------------- gain schedules
gs = {k: json.load(open(os.path.join(SRC_RUNS, tag, "gain_schedule.json"))) for k, tag in (("default", "baseline"), ("optimized", "eval_018"))}
STY = {"default": dict(color=C_BLUE, linestyle=(0, (4, 2)), linewidth=1.1), "optimized": dict(color=C_ORANGE, linestyle="-", linewidth=1.1)}
PANELS = [("omega_pc", r"$\omega_{\mathrm{pc}}$ (rad/s)", "(a)"), ("zeta_pc", r"$\zeta_{\mathrm{pc}}$", "(b)"),
          ("Kp", r"$k_p$ (s)", "(c)"), ("Ki", r"$k_i$", "(d)")]
fig, axes = plt.subplots(2, 2, figsize=(3.5, 2.95), sharex=True)
for ax, (key, lab, tag) in zip(axes.ravel(), PANELS):
    for U in (12, 18, 24):
        ax.axvline(U, color=GRID, linewidth=0.8, zorder=0)
    if key == "zeta_pc":
        ax.plot(gs["default"]["v"], gs["default"][key], color=INK, linewidth=1.1)
        ax.text(0.5, 0.07, "identical for\nboth controllers", transform=ax.transAxes, ha="center", va="bottom", fontsize=7, color=MUTED, linespacing=1.05)
    else:
        for k in ("default", "optimized"):
            ax.plot(gs[k]["v"], gs[k][key], label=k.capitalize(), **STY[k])
    if key == "omega_pc":
        for k in ("default", "optimized"):
            v = np.array(gs[k]["v"]); y = np.array(gs[k][key])
            ax.plot([12, 18, 24], np.interp([12, 18, 24], v, y), linestyle="none", marker="o", markersize=3.6,
                    markerfacecolor=STY[k]["color"], markeredgecolor="white", markeredgewidth=0.6)
    ax.set_ylabel(lab, labelpad=2)
    ax.grid(True, axis="y")
    ax.set_xlim(11.5, 25.5); ax.set_xticks([12, 15, 18, 21, 24])
    ax.text(0.04, 0.93, tag, transform=ax.transAxes, ha="left", va="top", fontsize=8, color=INK)
for ax in axes[1]:
    ax.set_xlabel("Wind speed (m/s)")
h, l = axes[0, 0].get_legend_handles_labels()
fig.legend(h[:2], l[:2], loc="upper center", ncol=2, frameon=False, handlelength=2.2, columnspacing=1.6, bbox_to_anchor=(0.54, 1.005))
fig.subplots_adjust(left=0.135, right=0.985, top=0.925, bottom=0.125, wspace=0.42, hspace=0.12)
fig.savefig(os.path.join(PAPER, "fig_gains.pdf"))
fig.savefig(os.path.join(PREV, "fig_gains.png"), dpi=220)
plt.close(fig)
for k in ("default", "optimized"):
    v = np.array(gs[k]["v"])
    print(k, "omega at 12/18/24:", np.round(np.interp([12, 18, 24], v, gs[k]["omega_pc"]), 3).tolist(),
          " kp, ki at 17.8:", round(float(np.interp(17.8, v, gs[k]["Kp"])), 3), round(float(np.interp(17.8, v, gs[k]["Ki"])), 4))
print("written: fig_wind.pdf, fig_gains.pdf")
