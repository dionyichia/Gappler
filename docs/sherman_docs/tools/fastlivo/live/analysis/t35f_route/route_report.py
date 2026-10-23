"""T3.5f route analyses: join degeneracy (deg_LABEL.csv), reference error (ref_LABEL.csv) and route features, plot, and print the alignment table.
usage: route_report.py OUT_PNG DEG_PREFIX REF_PREFIX TOPDOWN_PREFIX     (labels run1 run2 hd1; hd1 has degeneracy only)
Per 3 s reference interval: change of the FAST-LIVO2-minus-reference error vector (|delta e|, and its direction), against mean glass distance, mean yaw rate,
mean smallest horizontal information eigenvalue, and the angle between delta e and the weak horizontal direction (mean |cos| for unrelated directions is 0.64)."""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

out, degp, refp, topp = sys.argv[1:5]
load = lambda f: np.genfromtxt(f, delimiter=",", names=True)


def rank(a):
    return np.argsort(np.argsort(a)).astype(float)


def spearman(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(rank(a[m]), rank(b[m]))[0, 1]) if m.sum() > 3 else float("nan")


fig, axs = plt.subplots(3, 3, figsize=(20, 17))
for c, l in enumerate(("run1", "run2", "hd1")):
    d = load("%s_%s.csv" % (degp, l)); z = np.load("%s_%s.npz" % (topp, l)); org, res, cnt = z["org"], float(z["res"]), z["cnt"]
    ax = axs[0][c]
    ax.imshow(np.log1p(cnt).T, origin="lower", extent=[org[0], org[0] + cnt.shape[0] * res, org[1], org[1] + cnt.shape[1] * res], cmap="gray_r", vmax=np.log1p(cnt).max() * .6, alpha=.6)
    sc = ax.scatter(d["x"], d["y"], c=d["lam2_min"], s=26, cmap="coolwarm_r", vmin=0.09, vmax=0.16)
    a = np.radians(d["weak2_deg"]); k = slice(0, None, 2)
    ax.quiver(d["x"][k], d["y"][k], np.cos(a)[k], np.sin(a)[k], angles="xy", scale=14, width=.003, color="k", headwidth=0, headlength=0, headaxislength=0, pivot="mid")
    ax.set_xlim(-3, 5); ax.set_ylim(-4, 4.5); ax.set_aspect("equal"); ax.grid(alpha=.3); plt.colorbar(sc, ax=ax, fraction=.04, label="smallest horizontal info eigenvalue (share of info)")
    ax.set_title("%s: colour = weakest horizontal share, bars = weak direction" % l)
    ax = axs[1][c]
    ax.plot(d["t_s"], d["lam2_min"], "b-", label="all points"); ax.plot(d["t_s"], d["lam2_min_in"], "c--", label="inside glass box only")
    ax.set_ylabel("smallest horizontal info eigenvalue"); ax.set_xlabel("t (s)"); ax.legend(loc="upper left"); ax.grid(alpha=.3)
    ax2 = ax.twinx(); ax2.plot(d["t_s"], d["glass_dist_m"], "g-", alpha=.6); ax2.set_ylabel("distance to nearest glass plane (m), green", color="g")
    ax.set_title("%s: weak direction share and glass distance along time" % l)
    print("== %s degeneracy: lam2_min median %.3f p10 %.3f min %.3f at t=%.0f s (x %.1f y %.1f); share of scans below 0.11: %.0f %%; weak direction deg (10/50/90 pct) %s" % (
        l, np.median(d["lam2_min"]), np.percentile(d["lam2_min"], 10), d["lam2_min"].min(), d["t_s"][d["lam2_min"].argmin()], d["x"][d["lam2_min"].argmin()], d["y"][d["lam2_min"].argmin()],
        100 * (d["lam2_min"] < .11).mean(), np.percentile(d["weak2_deg"], [10, 50, 90]).round(0)))
    if l == "hd1":
        axs[2][c].axis("off"); continue
    r = load("%s_%s.csv" % (refp, l)); ok = r["accepted"] == 1
    ax = axs[2][c]; ax.plot(r["t_s"][ok], r["err_h"][ok], "ro-", label="|FAST-LIVO2 - reference| horizontal"); ax.axhline(0.07, color="gray", ls=":", label="reference's own error, about 0.07 m")
    ax.plot(r["t_s"][ok], r["err_z"][ok], "m.-", label="z"); ax.set_xlabel("t (s)"); ax.set_ylabel("m"); ax.grid(alpha=.3); ax.legend(loc="upper left")
    ax3 = ax.twinx(); ax3.plot(d["t_s"], d["yaw_deg"], "k-", alpha=.4); ax3.set_ylabel("yaw (deg), black")
    ax.set_title("%s: drift against the independent reference (handdriven1 map)" % l)
    t = r["t_s"][ok]; e = np.stack([r["err_x"][ok], r["err_y"][ok]], 1); de = np.diff(e, axis=0); mag = np.hypot(*de.T)
    mid = 0.5 * (t[1:] + t[:-1]); tab = []
    for i in range(len(mag)):
        w = (d["t_s"] >= t[i] - 0.5) & (d["t_s"] <= t[i + 1] + 0.5)
        yr = np.abs(np.diff(np.unwrap(np.radians(d["yaw_deg"][w])))).sum() / max(np.ptp(d["t_s"][w]), 1e-6) * 180 / np.pi
        ang = np.radians(d["weak2_deg"][w]).mean()
        wv = np.array([np.cos(np.median(np.radians(d["weak2_deg"][w]))), np.sin(np.median(np.radians(d["weak2_deg"][w])))])
        cosd = abs(de[i] @ wv) / max(mag[i], 1e-9)
        tab.append((mid[i], mag[i], d["glass_dist_m"][w].mean(), yr, d["lam2_min"][w].mean(), cosd))
    T = np.array(tab)
    print("== %s: error vs route; accepted windows %d, max err %.3f m at t=%.0f s, end err %.3f m" % (l, ok.sum(), r["err_h"][ok].max(), r["t_s"][ok][r["err_h"][ok].argmax()], r["err_h"][ok][-1]))
    print("   rank correlation of |delta e| per 3 s interval with: glass distance %+.2f, yaw rate %+.2f, weak-share %+.2f; mean |cos(delta e, weak dir)| %.2f (0.64 = unrelated)" % (
        spearman(T[:, 1], T[:, 2]), spearman(T[:, 1], T[:, 3]), spearman(T[:, 1], T[:, 4]), np.nanmean(T[:, 5])))
    top = np.argsort(-T[:, 1])[:5]
    print("   five largest 3 s error changes (t mid, |de| m, glass dist m, yaw rate deg/s, weak share): " + "; ".join("%.0f s %.3f %.2f %.1f %.3f" % tuple(T[i, :5]) for i in top))
    g = d["glass_dist_m"]; near = (g < 1.2)
    seg = (r["t_s"] > 30) & (r["t_s"] < 58) & ok
    print("   error in 30 to 58 s windows: mean %.3f m; outside them %.3f m. Scans closer than 1.2 m to a glass plane: %.0f %% of the run, of which in 30 to 58 s %.0f %%" % (
        r["err_h"][seg].mean(), r["err_h"][ok & ~seg].mean(), 100 * near.mean(), 100 * (near & (d["t_s"] > 30) & (d["t_s"] < 58)).sum() / max(near.sum(), 1)))
fig.tight_layout(); fig.savefig(out, dpi=70); print("wrote", out)
