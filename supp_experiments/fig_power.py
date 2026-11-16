"""
Generator-power figures of the manuscript, redrawn in the style of the other matplotlib figures:

  fig_power_ref.pdf    - generator power of the default and optimized controllers with the 22-MW reference
                         over the evaluation window (content of ch6_outputs/generator_power_with_reference.pdf)
  fig_power_detail.pdf - enlargement of 150-170 s and distribution of the power error
                         (lower two panels of ch6_outputs/fig6_5_power.pdf)

  python fig_power.py [preview_dir]
"""
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

runs = {}
for name, tag in (("default", "baseline"), ("optimized", "eval_018")):
    d = read_outb(os.path.join(SRC_RUNS, tag, OUTB))
    w = (d["Time"] >= 100) & (d["Time"] <= 300)
    runs[name] = (d["Time"][w], d["GenPwr"][w] / 1e3)
rmse = {k: float(np.sqrt(np.mean((p * 1e3 - 22000.0) ** 2))) for k, (t, p) in runs.items()}
print("RMSE (kW):", rmse)
LAB = {"default": f"Default (RMSE {rmse['default']:.1f} kW)", "optimized": f"Optimized (RMSE {rmse['optimized']:.1f} kW)"}
COL = {"default": C_BLUE, "optimized": C_ORANGE}

# ---------------------------------------------------------------- full window with the reference
fig, ax = plt.subplots(figsize=(3.5, 2.05))
for k in ("default", "optimized"):
    t, p = runs[k]
    ax.plot(t[::2], p[::2], color=COL[k], linewidth=0.55, alpha=0.95 if k == "default" else 0.85, label=LAB[k])
ax.axhline(22.0, color=INK, linewidth=0.9, linestyle=(0, (4, 2)), label="Reference (22 MW)")
ax.set_xlim(100, 300); ax.set_ylim(21.6, 22.5)
ax.set_xlabel("Time (s)"); ax.set_ylabel("Generator power (MW)")
ax.grid(True)
ax.legend(loc="upper center", ncol=1, frameon=True, framealpha=0.9, edgecolor="none", borderpad=0.2, labelspacing=0.2,
          bbox_to_anchor=(0.31, 1.0), handlelength=1.6)
fig.subplots_adjust(left=0.15, right=0.98, top=0.975, bottom=0.185)
fig.savefig(os.path.join(PAPER, "fig_power_ref.pdf"))
fig.savefig(os.path.join(PREV, "fig_power_ref.png"), dpi=220)
plt.close(fig)

# ---------------------------------------------------------------- enlargement and error distribution
fig, (a1, a2) = plt.subplots(2, 1, figsize=(3.5, 3.0))
for k in ("default", "optimized"):
    t, p = runs[k]
    w = (t >= 150) & (t <= 170)
    a1.plot(t[w], p[w], color=COL[k], linewidth=0.9, label=k.capitalize())
a1.axhline(22.0, color=INK, linewidth=0.8, linestyle=(0, (4, 2)))
a1.set_xlim(150, 170); a1.set_ylim(21.7, 22.4); a1.set_xticks([150, 155, 160, 165, 170])
a1.set_xlabel("Time (s)"); a1.set_ylabel("Generator power (MW)")
a1.grid(True)
a1.text(0.02, 0.94, "(a)", transform=a1.transAxes, ha="left", va="top", fontsize=8, color=INK,
        bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.85))
bins = np.linspace(-320, 320, 65)
for k in ("default", "optimized"):
    e = runs[k][1] * 1e3 - 22000.0
    a2.hist(e, bins=bins, density=True, histtype="step", color=COL[k], linewidth=1.0, label=k.capitalize())
a2.set_xlim(-320, 320)
a2.set_xlabel("Power error (kW)"); a2.set_ylabel("Density (1/kW)")
a2.grid(True)
a2.text(0.02, 0.94, "(b)", transform=a2.transAxes, ha="left", va="top", fontsize=8, color=INK)
h, l = a1.get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=2, frameon=False, handlelength=2.2, columnspacing=1.6, bbox_to_anchor=(0.57, 1.005))
fig.subplots_adjust(left=0.16, right=0.975, top=0.93, bottom=0.125, hspace=0.42)
fig.savefig(os.path.join(PAPER, "fig_power_detail.pdf"))
fig.savefig(os.path.join(PREV, "fig_power_detail.png"), dpi=220)
plt.close(fig)
print("written: fig_power_ref.pdf, fig_power_detail.pdf")
