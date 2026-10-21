"""T3.5f drift steps 1 and 2: overlay of the three /cloud_registered maps in the run 1 frame, and 0.5 m disagreement heat maps.
Needs out/step0_frames.json.  Maps: 5 cm voxels, height band 0.2-1.5 m above each run's floor (floor = lowest dominant z peak).
Tracks are the BASE position p_imu - R c (c = corrected constant 0.191 0.023 0.156, as analyze_spin.py), levelled, then moved into the run 1 frame.
Marks: run 1 odom readings from floor_marks (A read at the end of the loop; B, C after being pushed there).
usage: step12.py"""
import json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.spatial import cKDTree
import drift_common as D
R, P = D.R, D.P
C = np.array([0.191, 0.023, 0.156]); CELL = 0.5; VOX = 0.05; BAND = (0.2, 1.5); VMAX = 0.30
MARKS = {"A": (0.247, -0.202), "B": (2.262, -0.124), "C": (-0.045, 1.991)}
frames = D.load_frames(); labels = [l for l in ("run1", "run2", "hd1") if l in frames]
clouds, tracks, info = {}, {}, {}
for lab in labels:
    odom = np.loadtxt  # placeholder to keep names short
    od, _ = R.read_fast(D.BAGS[lab], t_max=0.1)
    odom_full = None
    import sqlite3, glob
    from rclpy.serialization import deserialize_message
    from nav_msgs.msg import Odometry
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(D.BAGS[lab] + "/*.db3")[0], uri=True)
    tid = {n: i for i, n in db.execute("select id, name from topics")}["/aft_mapped_to_init"]
    rows = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid,)):
        m = deserialize_message(bytes(d), Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
        rows.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
    odom = np.array(rows); Rt = R.level_rot(odom)
    base = np.array([odom[i, 1:4] - P.rot(odom[i, 4:8]) @ C for i in range(len(odom))]) @ Rt
    tracks[lab] = D.apply(frames[lab], base)
    pts, n = D.read_registered(D.BAGS[lab], Rt, vox=VOX)
    zf = pts[:, 2]; lo = np.percentile(zf, 20); h, e = np.histogram(zf[zf < lo], bins=np.arange(zf.min(), lo + 0.02, 0.02)); floor = e[np.argmax(h)] + 0.01
    sel = (pts[:, 2] - floor >= BAND[0]) & (pts[:, 2] - floor <= BAND[1])
    clouds[lab] = D.apply(frames[lab], pts[sel])
    info[lab] = dict(msgs=n, voxels=len(pts), band_voxels=int(sel.sum()), floor_z=float(floor))
    print("%s: %d non-empty /cloud_registered msgs, %d voxels at 5 cm, %d in band %.1f-%.1f m above floor (floor z %.3f in levelled frame)" % (lab, n, len(pts), sel.sum(), *BAND, floor), flush=True)
    np.savez_compressed("%s/map_%s.npz" % (D.OUT, lab), band=clouds[lab].astype(np.float32), track=tracks[lab])

# the bridge re-zeroes odom at the start BASE pose, so a mark reading is a displacement from the run 1 base start; shift into the common frame
MARKS = {k: (x + tracks["run1"][0, 0], y + tracks["run1"][0, 1]) for k, (x, y) in MARKS.items()}
lim = (-3.2, 4.2, -4.6, 4.2)
def decorate(ax, tracks_on=True):
    ax.add_patch(Rectangle((D.R.BOX[0], D.R.BOX[2]), D.R.BOX[1] - D.R.BOX[0], D.R.BOX[3] - D.R.BOX[2], fill=False, ls="--", lw=1.2, ec="k"))
    x0, x1, y0, y1 = D.R.ROOM
    ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color="c", lw=1.0, ls=":")
    for k, (x, y) in MARKS.items():
        ax.plot(x, y, "k*", ms=11); ax.annotate(k, (x, y), textcoords="offset points", xytext=(6, 6), fontsize=11, weight="bold")
    ax.set_xlim(lim[0], lim[1]); ax.set_ylim(lim[2], lim[3]); ax.set_aspect("equal"); ax.set_xlabel("x, run 1 frame (m)"); ax.set_ylabel("y (m)"); ax.grid(alpha=.2)

# ---- step 1
fig, ax = plt.subplots(figsize=(10.5, 10))
for lab in labels:
    xy = np.unique(np.round(clouds[lab][:, :2] / VOX).astype(np.int64), axis=0) * VOX
    ax.scatter(xy[:, 0], xy[:, 1], s=5, c=D.COL[lab], alpha=0.5, lw=0, label="%s map" % lab)
for lab in labels:
    t = tracks[lab]; ax.plot(t[:, 0], t[:, 1], color=D.COL[lab], lw=2.2, path_effects=None); ax.plot(*t[0, :2], "o", color=D.COL[lab], mec="k", ms=9); ax.plot(*t[-1, :2], "s", color=D.COL[lab], mec="k", ms=9)
decorate(ax)
ax.set_title("Three /cloud_registered maps (5 cm, 0.2-1.5 m band), run 1 frame. Lines: base tracks (circle start, square end)\nBlack dashed: replay glass box. Cyan dotted: approximate glass planes. Stars: marks A, B, C (run 1 odom readings)", fontsize=9)
ax.legend(markerscale=4, loc="upper left"); fig.tight_layout(); fig.savefig(D.OUT + "/step1_overlay.png", dpi=110); plt.close(fig)

# ---- step 2
def heat(src, dst, name):
    S, T = clouds[src], clouds[dst]; tree = cKDTree(T); d, _ = tree.query(S)
    nx, ny = int((lim[1] - lim[0]) / CELL) + 1, int((lim[3] - lim[2]) / CELL) + 1
    ix = np.floor((S[:, 0] - lim[0]) / CELL).astype(int); iy = np.floor((S[:, 1] - lim[2]) / CELL).astype(int)
    inb = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny); ix, iy, d = ix[inb], iy[inb], d[inb]
    G = np.full((ny, nx), np.nan)
    cid = iy * nx + ix; order = np.argsort(cid); cid, dsort = cid[order], d[order]
    cuts = np.flatnonzero(np.diff(cid)) + 1
    for c, dv in zip(cid[np.r_[0, cuts]], np.split(dsort, cuts)):
        if len(dv) >= 20: G[c // nx, c % nx] = np.median(dv)
    dd, _ = cKDTree(np.unique(np.round(T[:, :2] / VOX).astype(np.int64), axis=0) * VOX).query(np.array([[lim[0] + (i + .5) * CELL, lim[2] + (j + .5) * CELL] for j in range(ny) for i in range(nx)]), distance_upper_bound=1.5)
    ok = np.isfinite(G); v = G[ok]
    # cell is "covered" if the target has points in/near the cell: a large median distance with no target nearby means no overlap, not disagreement
    cov = (dd.reshape(ny, nx) < 0.5)   # target has a point within 0.5 m of the cell centre in plan
    G2 = np.where(cov, G, np.nan); ok2 = np.isfinite(G2); v2 = G2[ok2]
    fig, ax = plt.subplots(figsize=(9.5, 9.2))
    im = ax.pcolormesh(lim[0] + CELL * np.arange(nx + 1), lim[2] + CELL * np.arange(ny + 1), np.ma.masked_invalid(G2), cmap="magma_r", vmin=0, vmax=VMAX)
    ax.set_facecolor("#dddddd")
    for lab in (src, dst): ax.plot(tracks[lab][:, 0], tracks[lab][:, 1], color=D.COL[lab], lw=1.5)
    decorate(ax); plt.colorbar(im, ax=ax, shrink=.75, label="median NN distance per 0.5 m cell (m); grey = no data / no target within 0.5 m")
    ax.set_title("%s -> %s: %d cells, median of cell medians %.3f m, 90th pct %.3f m, cells > 0.10 m: %d%%" % (src, dst, ok2.sum(), np.median(v2), np.percentile(v2, 90), 100 * (v2 > .10).mean()), fontsize=10)
    fig.tight_layout(); fig.savefig(D.OUT + "/step2_heat_%s.png" % name, dpi=110); plt.close(fig)
    # near glass vs interior (cell centres)
    cx = lim[0] + (np.arange(nx) + .5) * CELL; cy = lim[2] + (np.arange(ny) + .5) * CELL
    XX, YY = np.meshgrid(cx, cy); gd = D.R.glass_distance(np.column_stack([XX.ravel(), YY.ravel()])).reshape(ny, nx)
    near = ok2 & (gd < 1.2) & (gd > -0.3); inner = ok2 & (gd >= 1.2)
    print("%s -> %s: points %d vs %d; cells %d (of %d with source points); median %.3f p90 %.3f max %.3f | >0.10 m: %d%% | cells within 1.2 m of glass: n=%d median %.3f ; interior: n=%d median %.3f" % (
        src, dst, len(S), len(T), ok2.sum(), ok.sum(), np.median(v2), np.percentile(v2, 90), v2.max(), 100 * (v2 > .1).mean(), near.sum(), np.median(G2[near]) if near.any() else np.nan, inner.sum(), np.median(G2[inner]) if inner.any() else np.nan))
    return G2

heat("run1", "run2", "run1_run2")
if "hd1" in labels:
    heat("run1", "hd1", "run1_hd1"); heat("run2", "hd1", "run2_hd1")
json.dump(info, open(D.OUT + "/step12_info.json", "w"))
