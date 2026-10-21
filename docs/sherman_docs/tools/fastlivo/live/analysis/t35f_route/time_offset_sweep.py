"""T3.5f route analysis 3: is the pose stream offset in time from the LiDAR geometry? Map-free test. For 2 s windows taken while the robot moves, place the scans
with the odometry pose at (scan stamp + 0.05 s + DELTA), interpolated (linear position, normalised linear quaternion), for a sweep of DELTA, and measure how
thick the surfaces are: median sqrt of the smallest eigenvalue of the covariance of each point's 10 nearest neighbours. A wrong time offset smears surfaces
by speed x error, so the thickness is smallest at the right DELTA. DELTA > 0 means the scans belong to a later pose than their stamp says.
usage: time_offset_sweep.py LABEL=BAG_DIR [...]"""
import sys
import numpy as np
from scipy.spatial import cKDTree
import route_common as R
P = R.P
DELTAS = np.round(np.arange(-0.2, 0.61, 0.05), 2)
WIN, STEP, MIN_SPEED, MIN_YAW = 2.0, 3.0, 0.15, 10.0


def pose_at(odom, t):
    i = int(np.clip(np.searchsorted(odom[:, 0], t), 1, len(odom) - 1)); a = (t - odom[i - 1, 0]) / max(odom[i, 0] - odom[i - 1, 0], 1e-9); a = min(max(a, 0), 1)
    q = (1 - a) * odom[i - 1, 4:8] + a * odom[i, 4:8] * np.sign(odom[i - 1, 4:8] @ odom[i, 4:8] or 1); q /= np.linalg.norm(q)
    return P.rot(q), (1 - a) * odom[i - 1, 1:4] + a * odom[i, 1:4]


def thickness(X, rng=np.random.RandomState(0)):
    tree = cKDTree(X); s = X[rng.choice(len(X), min(6000, len(X)), replace=False)]
    _, idx = tree.query(s, k=10); nb = X[idx]; nb = nb - nb.mean(1, keepdims=True)
    w = np.linalg.eigvalsh(np.einsum("nki,nkj->nij", nb, nb) / 10)
    return float(np.median(np.sqrt(np.maximum(w[:, 0], 0))))


for arg in sys.argv[1:]:
    label, bag = arg.split("=", 1)
    odom, scans = R.read_fast(bag)
    pos, yaw = R.session_track(odom); stamps = np.array([s for s, _ in scans]); t0 = odom[0, 0]
    res = []
    for ts in np.arange(0, stamps[-1] - t0 - WIN, STEP):
        sel = [k for k in range(len(scans)) if ts <= stamps[k] - t0 < ts + WIN]
        i0, i1 = np.searchsorted(odom[:, 0], [t0 + ts, t0 + ts + WIN])
        speed = np.hypot(*(pos[min(i1, len(pos) - 1), :2] - pos[i0, :2])) / WIN
        yr = np.abs(np.diff(np.unwrap(np.radians(yaw[i0:i1 + 1])))).sum() / WIN * 180 / np.pi
        if len(sel) < 10 or (speed < MIN_SPEED and yr < MIN_YAW):
            continue
        row = []
        for dl in DELTAS:
            Xs = []
            for k in sel:
                s, pts = scans[k]; r = np.linalg.norm(pts, axis=1); pts = pts[(r > 1.0) & (r < 10.0)]
                Rm, t = pose_at(odom, s + dl)
                Xs.append((pts + P.T_EXT) @ Rm.T + t)
            row.append(thickness(np.vstack(Xs)))
        res.append((ts, speed, yr, row))
    th = np.array([r[3] for r in res]); best = DELTAS[th.argmin(1)]
    print("%s: %d moving windows (speed >= %.2f m/s or yaw rate >= %.0f deg/s)" % (label, len(res), MIN_SPEED, MIN_YAW))
    print("   mean thickness (mm) by DELTA: " + "  ".join("%+.2f:%.1f" % (d, 1000 * m) for d, m in zip(DELTAS, th.mean(0))))
    print("   best DELTA per window: median %+.2f s, quartiles %s; windows where DELTA=0 is within 2%% of the best: %d of %d" % (
        np.median(best), np.percentile(best, [25, 75]), int((th[:, list(DELTAS).index(0.0)] <= th.min(1) * 1.02).sum()), len(res)))
    print("   thickness at best vs at DELTA=0 (mean, mm): %.1f vs %.1f" % (1000 * th.min(1).mean(), 1000 * th[:, list(DELTAS).index(0.0)].mean()))
    print("   per window (t, speed, yaw rate, best DELTA): " + "; ".join("%.0f s %.2f %.0f %+.2f" % (r[0], r[1], r[2], b) for r, b in zip(res, best)))
