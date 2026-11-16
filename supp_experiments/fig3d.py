"""
3-D figures of the manuscript (matplotlib):

  fig_surface3d.pdf   - surrogate response surfaces over (omega_pc(12), omega_pc(18)) fitted to the 35
                        simulated candidates (20 from the optimization, 15 from random search):
                        power-error objective, generator-speed RMSE, tower-base fore-aft moment std
  fig_waterfall3d.pdf - rotor speed against time for the sweep of omega_pc(18): settles / keeps oscillating

  python fig3d.py [preview_dir]      PNG previews are written to preview_dir (default: outputs/preview)

Colours follow one rule each: magnitude = one-hue blue ramp (darker = larger); the two states of the
sweep = two categorical hues (blue, orange) that are also separated by the legend and by position.
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from mpl_toolkits.mplot3d.art3d import PolyCollection

from posthoc_analysis import gp_fit, gp_predict, gp_loo
from supp_common import RUNS, SRC_RUNS, OUT, OUTB, read_outb, ref_metrics

PAPER = r"D:\experiment\paper_ieee_draft\figures"
PREV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "preview")
os.makedirs(PREV, exist_ok=True)

BLUE_RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf",
             "#1c5cab", "#184f95", "#104281", "#0d366b"]
SEQ = LinearSegmentedColormap.from_list("blue_ramp", BLUE_RAMP)
C_BLUE, C_ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#d9d8d2"
BOUNDS = np.array([[0.1, 0.2], [0.1, 0.2], [0.1, 0.5]])

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "mathtext.fontset": "stix",
    "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "pdf.fonttype": 42,
})


def style3d(ax):
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor("white")
        axis.pane.set_edgecolor(GRID)
        axis._axinfo["grid"].update({"color": GRID, "linewidth": 0.4, "linestyle": "-"})
        axis.line.set_color(MUTED)
        axis.line.set_linewidth(0.5)
    ax.tick_params(pad=-2, length=2, width=0.4)


# ----------------------------------------------------------------------------- data of the 35 candidates
bo = [ref_metrics(f"eval_{i:03d}") for i in range(1, 21)]
om_bo = [json.load(open(os.path.join(SRC_RUNS, f"eval_{i:03d}", "parameters.json")))["omega_pc"] for i in range(1, 21)]
rnd = [json.load(open(os.path.join(RUNS, f"rand_{i:03d}", "metrics.json"))) for i in range(6, 21)]
W = np.array(om_bo + [m["omega_pc"] for m in rnd])
is_bo = np.array([True] * 20 + [False] * 15)
QUANT = [("J_power_mse_kW2", 1e-3, r"Power-error objective $J$ ($10^{3}$ kW$^{2}$)"),
         ("genspd_rmse_rpm", 1.0, "Generator-speed RMSE (rpm)"),
         ("twr_fa_std_kNm", 1e-3, "Tower fore-aft moment std (MN$\\cdot$m)")]
X = (W - BOUNDS[:, 0]) / (BOUNDS[:, 1] - BOUNDS[:, 0])
n = 41
g2, g3 = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n), indexing="ij")
best = int(np.argmin([m["J_power_mse_kW2"] for m in bo]))
info = {}
surf = []
AVG = np.linspace(0.02, 0.98, 13)                     # omega_pc(12) is averaged out (partial dependence)
for key, sc, title in QUANT:
    yraw = np.array([m[key] for m in bo + rnd]) * sc
    y = (yraw - yraw.mean()) / yraw.std()
    ls, noise, _ = gp_fit(X, y)
    loo = gp_loo(X, y, ls, noise)
    z = np.mean([gp_predict(X, y, ls, noise, np.column_stack((np.full(g2.size, a), g2.ravel(), g3.ravel()))) for a in AVG], axis=0)
    z = z.reshape(n, n) * yraw.std() + yraw.mean()
    rng = np.random.RandomState(1)
    A = rng.uniform(size=(4000, 3)); B = rng.uniform(size=(4000, 3))
    fA, fB = gp_predict(X, y, ls, noise, A), gp_predict(X, y, ls, noise, B)
    var = np.var(np.concatenate((fA, fB)))
    ST = []
    for i in range(3):
        AB = A.copy(); AB[:, i] = B[:, i]
        ST.append(float(0.5 * np.mean((fA - gp_predict(X, y, ls, noise, AB)) ** 2) / var))
    info[key] = {"loo_r2": float(1 - np.sum((y - loo) ** 2) / np.sum(y ** 2)), "length_scales": ls.tolist(), "noise": noise,
                 "sobol_total": ST, "surface_min": float(z.min()), "surface_max": float(z.max()),
                 "corr_w2": float(np.corrcoef(W[:, 1], yraw)[0, 1])}
    surf.append((yraw, z, title))
with open(os.path.join(OUT, "fig3d_info.json"), "w") as f:
    json.dump({"n_points": len(W), "averaged_over": "omega_pc(12)", "quantities": info}, f, indent=1)
print(json.dumps(info, indent=1))

G2 = BOUNDS[1, 0] + g2 * (BOUNDS[1, 1] - BOUNDS[1, 0])
G3 = BOUNDS[2, 0] + g3 * (BOUNDS[2, 1] - BOUNDS[2, 0])
fig = plt.figure(figsize=(7.16, 2.3))
for k, (yraw, z, title) in enumerate(surf):
    ax = fig.add_axes([0.005 + 0.333 * k, 0.06, 0.325, 0.95], projection="3d", computed_zorder=False)
    style3d(ax)
    ax.plot_surface(G2, G3, z, cmap=SEQ, linewidth=0.15, edgecolor="white", rstride=4, cstride=4, antialiased=True, alpha=0.92, zorder=1)
    lift = 0.012 * (yraw.max() - yraw.min())
    ax.scatter(W[~is_bo, 1], W[~is_bo, 2], yraw[~is_bo] + lift, s=13, marker="s", facecolor="white", edgecolor=INK, linewidth=0.7,
               depthshade=False, zorder=3, label="Random search")
    ax.scatter(W[is_bo, 1], W[is_bo, 2], yraw[is_bo] + lift, s=15, marker="o", facecolor=C_ORANGE, edgecolor="white", linewidth=0.5,
               depthshade=False, zorder=4, label="Bayesian optimization")
    ax.scatter([W[best, 1]], [W[best, 2]], [yraw[best] + lift], s=75, marker="*", facecolor=C_ORANGE, edgecolor=INK, linewidth=0.6,
               depthshade=False, zorder=5, label="Best candidate")
    ax.set_xlabel(r"$\omega_{\mathrm{pc}}^{(2)}$ (rad/s)", labelpad=-6)
    ax.set_ylabel(r"$\omega_{\mathrm{pc}}^{(3)}$ (rad/s)", labelpad=-6)
    ax.set_xticks([0.10, 0.15, 0.20]); ax.set_yticks([0.2, 0.3, 0.4, 0.5])
    ax.set_xlim(0.1, 0.2); ax.set_ylim(0.1, 0.5)
    ax.view_init(elev=24, azim=-58 if k < 2 else -125)      # (c) rises with omega_pc(18): seen from the other side
    ax.set_box_aspect((1, 1, 0.78), zoom=0.9)
    fig.text(0.005 + 0.333 * k + 0.1625, 0.95, f"({'abc'[k]}) {title}", ha="center", va="center", fontsize=8, color=INK)
    if k == 0:
        h, l = ax.get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=3, frameon=False, handletextpad=0.3, columnspacing=1.6, bbox_to_anchor=(0.5, -0.02))
fig.savefig(os.path.join(PAPER, "fig_surface3d.pdf"))
fig.savefig(os.path.join(PREV, "fig_surface3d.png"), dpi=220)
plt.close(fig)

# ----------------------------------------------------------------------------- waterfall of the sweep
runs = [("0.10", os.path.join(RUNS, "sweep_w2_0.100", OUTB)), ("0.15", os.path.join(RUNS, "sweep_w2_0.150", OUTB)),
        ("0.20", os.path.join(SRC_RUNS, "sens_i1_eval_018", OUTB)), ("0.24", os.path.join(RUNS, "sweep_w2_0.240", OUTB)),
        ("0.25", os.path.join(RUNS, "sweep_w2_0.250", OUTB)), ("0.26", os.path.join(RUNS, "sweep_w2_0.260", OUTB)),
        ("0.30", os.path.join(RUNS, "sweep_w2_0.300", OUTB)), ("0.35", os.path.join(RUNS, "sweep_w2_0.350", OUTB)),
        ("0.40", os.path.join(RUNS, "sweep_w2_0.400", OUTB)), ("0.50", os.path.join(RUNS, "sweep_w2_0.500", OUTB))]
fig = plt.figure(figsize=(3.5, 2.95))
ax = fig.add_subplot(111, projection="3d", computed_zorder=False)
style3d(ax)
Z0 = 3.0
state = {}
for k in range(len(runs) - 1, -1, -1):                 # far to near
    lab, path = runs[k]
    d = read_outb(path)
    t, rs = d["Time"][::20], d["RotSpeed"][::20]        # 5 Hz
    late = np.std(d["RotSpeed"][(d["Time"] >= 100) & (d["Time"] < 150)]) if d["Time"][-1] >= 150 else np.std(d["RotSpeed"][d["Time"] >= 100])
    osc = late > 0.2        # rotor-speed std over 100-150 s: 0.06-0.14 rpm once settled, 0.25 rpm and more otherwise
    state[lab] = {"speed_std_100_150": float(late), "oscillating": bool(osc), "t_end": float(d["Time"][-1])}
    col = C_ORANGE if osc else C_BLUE
    verts = [(t[0], Z0)] + list(zip(t, np.maximum(rs, Z0))) + [(t[-1], Z0)]
    pc = PolyCollection([verts], facecolors="white", edgecolors="none", alpha=0.88, zorder=2 * (len(runs) - k))
    ax.add_collection3d(pc, zs=k, zdir="y")
    ax.plot(t, np.full_like(t, k, dtype=float), rs, color=col, linewidth=0.7, zorder=2 * (len(runs) - k) + 1)
print(json.dumps(state, indent=1))
ax.set_xlim(0, 300); ax.set_ylim(-0.6, len(runs) - 0.4); ax.set_zlim(Z0, 10.6)
ax.set_xticks([0, 100, 200, 300])
ax.set_yticks(range(len(runs))); ax.set_yticklabels([r[0] for r in runs])
ax.set_zticks([4, 6, 8, 10])
ax.set_xlabel("Time (s)", labelpad=-6)
ax.set_ylabel(r"$\omega_{\mathrm{pc}}^{(2)}$ (rad/s)", labelpad=1)
ax.set_zlabel("Rotor speed (rpm)", labelpad=-7)
ax.view_init(elev=30, azim=-62)
ax.set_box_aspect((1.25, 1.5, 0.7), zoom=0.98)
ax.tick_params(axis="y", pad=-3)
from matplotlib.lines import Line2D
fig.legend(handles=[Line2D([0], [0], color=C_BLUE, lw=1.2, label="Settled at 100 s"),
                    Line2D([0], [0], color=C_ORANGE, lw=1.2, label="Oscillation continues after 100 s")],
           loc="upper left", bbox_to_anchor=(0.02, 0.995), frameon=False, handlelength=1.6, ncol=2, columnspacing=1.2)
ax.set_position([-0.07, -0.03, 1.07, 1.04])
fig.savefig(os.path.join(PAPER, "fig_waterfall3d.pdf"))
fig.savefig(os.path.join(PREV, "fig_waterfall3d.png"), dpi=220)
plt.close(fig)
print("figures written to", PAPER, "previews in", PREV)
