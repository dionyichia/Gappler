"""T3.5f drift steps 3 and 4: plots and the along-route feature table. Reads out/step3_*.csv (step3.py), out/step4_deg_*.csv (the degeneracy.py output of the
earlier route note, copied unchanged), out/map_*.npz and out/step0_frames.json. Writes step3_timeseries.png, step3_map.png, step4_weak.png and prints
rank correlations and a 10 s table.  usage: step34_plot.py"""
import json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.stats import spearmanr
import drift_common as D
OUT = D.OUT; frames = D.load_frames()
ref_err = 0.07
def load(p):
    a = np.genfromtxt(p, delimiter=",", names=True); return a
S = {(r, d): load("%s/step3_%s_%s.csv" % (OUT, r, d)) for r in ("run1", "run2") for d in ("d015", "d000")}
G = {r: load("%s/step4_deg_%s.csv" % (OUT, r)) for r in ("run1", "run2", "hd1")}
maps = {r: np.load("%s/map_%s.npz" % (OUT, r)) for r in ("run1", "run2", "hd1")}
MARKS = {"A": (0.247, -0.202), "B": (2.262, -0.124), "C": (-0.045, 1.991)}
b0 = maps["run1"]["track"][0, :2]; MARKS = {k: (x + b0[0], y + b0[1]) for k, (x, y) in MARKS.items()}
lim = (-3.2, 4.2, -4.6, 4.2)

def under(ax, faint=True):
    for r in ("run1", "run2", "hd1"):
        xy = maps[r]["band"][:, :2]; ax.scatter(xy[:, 0], xy[:, 1], s=2, c="0.6", alpha=0.25, lw=0)
    ax.add_patch(Rectangle((D.R.BOX[0], D.R.BOX[2]), D.R.BOX[1] - D.R.BOX[0], D.R.BOX[3] - D.R.BOX[2], fill=False, ls="--", lw=1, ec="k"))
    x0, x1, y0, y1 = D.R.ROOM; ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color="c", lw=1, ls=":")
    for k, (x, y) in MARKS.items():
        ax.plot(x, y, "k*", ms=10); ax.annotate(k, (x, y), textcoords="offset points", xytext=(5, 5), weight="bold")
    ax.set_xlim(lim[0], lim[1]); ax.set_ylim(lim[2], lim[3]); ax.set_aspect("equal"); ax.grid(alpha=.2); ax.set_xlabel("x, run 1 frame (m)"); ax.set_ylabel("y (m)")

# ---- step 3 time series
fig, axs = plt.subplots(4, 2, figsize=(13, 11), sharex="col")
for c, r in enumerate(("run1", "run2")):
    a15, a0, g = S[(r, "d015")], S[(r, "d000")], G[r]
    ax = axs[0, c]; ax.axhspan(0, ref_err, color="0.9"); ax.plot(a0["t_s"], a0["eh"], label="pose at scan stamp (prototype)"); ax.plot(a15["t_s"], a15["eh"], label="pose at stamp + 0.15 s")
    ax.set_title("%s: FAST-LIVO2 minus handdriven1 reference (grey = reference's own ~7 cm)" % r, fontsize=10); ax.set_ylabel("horizontal error (m)"); ax.legend(fontsize=8)
    ax = axs[1, c]; ax.plot(a0["t_s"], a0["e_along"], label="along track, stamp"); ax.plot(a15["t_s"], a15["e_along"], label="along track, +0.15 s"); ax.plot(a15["t_s"], a15["e_cross"], ":", label="cross track, +0.15 s")
    ax2 = ax.twinx(); ax2.plot(a15["t_s"], a15["speed"], color="0.5", lw=1); ax2.set_ylabel("speed (m/s)", color="0.4"); ax.set_ylabel("error component (m)"); ax.legend(fontsize=8)
    ax = axs[2, c]; ax.plot(a0["t_s"], a0["dyaw_deg"], label="stamp"); ax.plot(a15["t_s"], a15["dyaw_deg"], label="+0.15 s"); ax.set_ylabel("yaw error (deg)")
    ax3 = ax.twinx(); ax3.plot(a15["t_s"], np.abs(a15["yawrate_dps"]), color="0.5", lw=1); ax3.set_ylabel("|yaw rate| (deg/s)", color="0.4"); ax.legend(fontsize=8)
    ax = axs[3, c]; ax.plot(g["t_s"], g["lam2_min"], color="C3", label="smallest horizontal eigenvalue (info share)"); ax.set_ylabel("lambda_min"); ax.set_xlabel("t (s)")
    ax4 = ax.twinx(); ax4.plot(a15["t_s"], a15["glass_dist"], color="c", label="distance to glass plane"); ax4.plot(a15["t_s"], a15["wall_dist"], color="k", lw=1, label="clearance to nearest map point"); ax4.set_ylabel("m"); ax4.legend(fontsize=8, loc="upper right"); ax.legend(fontsize=8, loc="lower left")
fig.tight_layout(); fig.savefig(OUT + "/step3_timeseries.png", dpi=100); plt.close(fig)

# ---- step 3 map
fig, axs = plt.subplots(2, 2, figsize=(13, 13))
for c, r in enumerate(("run1", "run2")):
    for rr, d in enumerate(("d015", "d000")):
        ax = axs[rr, c]; under(ax); a = S[(r, d)]
        sc = ax.scatter(a["x1"], a["y1"], c=a["eh"], s=26, cmap="magma_r", vmin=0, vmax=0.13, zorder=3)
        ax.plot(*maps["hd1"]["track"][:, :2].T, color=D.COL["hd1"], lw=.8, alpha=.6)
        ax.set_title("%s, %s" % (r, "pose at stamp + 0.15 s" if d == "d015" else "pose at scan stamp"), fontsize=10)
        i = int(np.nanargmax(a["eh"])); ax.annotate("max %.2f m, t=%.0f s" % (a["eh"][i], a["t_s"][i]), (a["x1"][i], a["y1"][i]), xytext=(1.5, 3.3), arrowprops=dict(arrowstyle="->"), fontsize=9)
plt.colorbar(sc, ax=axs, shrink=.5, label="horizontal error (m)"); fig.savefig(OUT + "/step3_map.png", dpi=100); plt.close(fig)

# ---- step 4 weak directions on the common map
fig, axs = plt.subplots(1, 3, figsize=(20, 7.5))
for ax, r in zip(axs, ("run1", "run2", "hd1")):
    g = G[r]; F = frames[r]; xy = np.column_stack([g["x"], g["y"], np.zeros(len(g))]); p = D.apply(F, xy)
    ang = np.radians(g["weak2_deg"] + math.degrees(math.atan2(F[1, 0], F[0, 0])))
    under(ax); sc = ax.scatter(p[:, 0], p[:, 1], c=g["lam2_min"], s=30, cmap="viridis", vmin=0.08, vmax=0.14, zorder=3)
    ax.quiver(p[:, 0], p[:, 1], np.cos(ang), np.sin(ang), pivot="mid", scale=11, width=0.003, headwidth=0, headlength=0, headaxislength=0, color="k", zorder=4)
    ax.set_title("%s: lambda_min median %.3f, min %.3f" % (r, np.median(g["lam2_min"]), g["lam2_min"].min()), fontsize=9)
plt.colorbar(sc, ax=axs, shrink=.6, label="smallest horizontal eigenvalue of mean(n n^T); tick = weak direction"); fig.savefig(OUT + "/step4_weak.png", dpi=100); plt.close(fig)

# ---- features: rank correlation of the error with route features (windows), and a 10 s table
print("rank correlation (Spearman) of horizontal error with route features, windows of 1 s:")
for r in ("run1", "run2"):
    g = G[r]
    for d in ("d015", "d000"):
        a = S[(r, d)]; lam = np.interp(a["t_s"], g["t_s"], g["lam2_min"]); ok = np.isfinite(a["eh"])
        res = []
        for nm, v in (("speed", a["speed"]), ("|yaw rate|", np.abs(a["yawrate_dps"])), ("glass dist", a["glass_dist"]), ("clearance", a["wall_dist"]), ("lam_min", lam)):
            rho, pv = spearmanr(a["eh"][ok], v[ok]); res.append("%s %+.2f" % (nm, rho))
        print("  %s %s: n=%d  %s" % (r, d, ok.sum(), " | ".join(res)))
print("10 s table (delta 0.15 error, mean per 10 s; lam_min = smallest horizontal eigenvalue; weak = weak direction deg in run 1 frame):")
for r in ("run1", "run2"):
    a, g = S[(r, "d015")], G[r]; F = frames[r]; yawF = math.degrees(math.atan2(F[1, 0], F[0, 0]))
    print(" ", r); print("   t(s)  path(m) err_h(m) err_h_stamp(m) speed yawrate glass clear lam_min weak")
    a0 = S[(r, "d000")]
    for t in range(0, int(a["t_s"][-1]), 10):
        m = (a["t_s"] >= t) & (a["t_s"] < t + 10); mg = (g["t_s"] >= t) & (g["t_s"] < t + 10)
        if m.sum() == 0: continue
        print("   %3d-%3d %5.1f  %.3f  %.3f   %.2f  %+5.1f  %.2f  %.2f  %.3f  %3.0f" % (t, t + 10, a["path_m"][m][-1], np.nanmean(a["eh"][m]), np.nanmean(a0["eh"][m]), a["speed"][m].mean(), a["yawrate_dps"][m].mean(), a["glass_dist"][m].mean(), a["wall_dist"][m].mean(), g["lam2_min"][mg].mean() if mg.any() else np.nan, (np.median(g["weak2_deg"][mg]) + yawF) % 180 if mg.any() else np.nan))
