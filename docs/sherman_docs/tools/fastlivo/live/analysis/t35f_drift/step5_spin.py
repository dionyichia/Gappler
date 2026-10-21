"""T3.5f drift step 5: rotation-coupled error from the two in-place spins of T3.5d (spin-corrected: extrinsic_T [-0.011,-0.02329,0.04412]; spin-precorrection: negated).
(a) recorded mapper translation: still-to-still start/end, excursion, residual after a fixed-pivot rotation fit (lever arm removed), and the LiDAR check:
    0.5 s windows at every 45 deg of swept yaw registered onto the first window (placed with the recorded poses) -> correction = pose error that grows with turning.
(b) map sharpness: the same scans placed with each run's own poses and own extrinsic, per-point pose interpolation (offset_time), plane thickness in 0.2 m cells,
    swept over a pose-time offset delta; plus the cross-placement (other run's extrinsic) as a sanity line.
usage: step5_spin.py [a|b]"""
import glob, math, sqlite3, sys
import numpy as np
from scipy.spatial.transform import Rotation, Slerp
import drift_common as D
R, P = D.R, D.P
BASE = D.L + "/t35d-attended-20261020.raLTgE"
RUNS = {"corrected": BASE + "/spin-corrected/bag", "precorrection": BASE + "/spin-precorrection/bag"}
T_USED = {"corrected": np.array([-0.011, -0.02329, 0.04412]), "precorrection": np.array([0.011, 0.02329, -0.04412])}
C_BASE = {"corrected": np.array([0.191, 0.023, 0.156]), "precorrection": np.array([0.169, -0.023, 0.244])}   # bridge constants (analyze_spin.py)
RMAX = 8.0


def load(bag):
    from rclpy.serialization import deserialize_message
    from nav_msgs.msg import Odometry
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True); tid = {n: i for i, n in db.execute("select id, name from topics")}
    od = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid["/aft_mapped_to_init"],)):
        m = deserialize_message(bytes(d), Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
        od.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
    sc = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid["/livox/lidar"],)):
        m = R.conv.decode_custom_msg_numpy(bytes(d)); a = m["array"]
        sc.append((m["sec"] + m["nanosec"] * 1e-9, a["t"].astype(np.float64) * 1e-9, np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64)))
    return np.array(od), sc


def yaw_unwrapped(od):
    return np.degrees(np.unwrap([math.atan2(2 * (r[7] * r[6] + r[4] * r[5]), 1 - 2 * (r[5] ** 2 + r[6] ** 2)) for r in od]))


def part_a():
    for name, bag in RUNS.items():
        od, sc = load(bag); t = od[:, 0] - od[0, 0]; yaw = yaw_unwrapped(od); rate = np.gradient(yaw, t)
        mv = np.flatnonzero(np.abs(rate) > 5); i0, i1 = max(mv[0] - 5, 0), min(mv[-1] + 5, len(od) - 1)
        print("== %s: %d poses, %.1f s, turn %.1f s to %.1f s, swept %.1f deg" % (name, len(od), t[-1], t[i0], t[i1], yaw[i1] - yaw[i0]))
        c = C_BASE[name]; base = np.array([od[i, 1:4] - P.rot(od[i, 4:8]) @ c for i in range(len(od))])
        # still-to-still. the precorrection bag has no real still start (turn begins at 0.2 s), so take the first/last 5 poses (0.25 s)
        s0, s1 = od[:5, 1:4].mean(0), od[-5:, 1:4].mean(0); b0, b1 = base[:5].mean(0), base[-5:].mean(0)
        dyaw = yaw[-5:].mean() - yaw[:5].mean()
        print("  (a1) mapper start->end, raw IMU pose: dx %+.3f dy %+.3f dz %+.3f m (%.3f horizontal), yaw change %.1f deg" % (*(s1 - s0), math.hypot(*(s1 - s0)[:2]), dyaw))
        print("       same with the bridge constant removed (base): dx %+.3f dy %+.3f (%.3f); yaw mismatch from a whole turn %.2f deg x lever 0.19 m = %.3f m" % (*(b1 - b0)[:2], math.hypot(*(b1 - b0)[:2]), (dyaw + 360 * round(-dyaw / 360)), 0.19 * abs(math.radians(dyaw + 360 * round(-dyaw / 360)))))
        ex = np.hypot(*(base[i0:i1 + 1, :2] - b0[:2]).T); exr = np.hypot(*(od[i0:i1 + 1, 1:3] - s0[:2]).T)
        print("       max excursion from the start: raw IMU %.3f m (a circle of the lever arm), base %.3f m" % (exr.max(), ex.max()))
        yw = np.radians(yaw[i0:i1 + 1]); Pxy = od[i0:i1 + 1, 1:3]; tt = (t[i0:i1 + 1] - t[i0]) / (t[i1] - t[i0])
        for order, lab in ((0, "fixed pivot, no drift"), (1, "fixed pivot plus a steady slip")):
            cols = []
            for ax in (0, 1):
                for k in range(order + 1):
                    cc = np.zeros(len(tt) * 2); cc[ax::2] = tt ** k; cols.append(cc)
            cx = np.zeros(len(tt) * 2); cx[0::2] = np.cos(yw); cx[1::2] = np.sin(yw); cy = np.zeros(len(tt) * 2); cy[0::2] = -np.sin(yw); cy[1::2] = np.cos(yw)
            A = np.column_stack(cols + [cx, cy]); y = Pxy.reshape(-1); sol = np.linalg.lstsq(A, y, rcond=None)[0]; res = (A @ sol - y).reshape(-1, 2)
            print("       (a2) %-30s lever (%.3f, %.3f) m: residual rms %.4f m, max %.4f m  [translation not explained by a rigid turn about one point]" % (lab, sol[-2], sol[-1], math.sqrt((res ** 2).sum(1).mean()), np.hypot(*res.T).max()))
        # LiDAR check at every 45 deg of swept yaw
        sc_t = np.array([s for s, _, _ in sc]); targets = [yaw[i0] + k * (yaw[i1] - yaw[i0]) / 8 for k in range(9)]
        def window(yaw_t):
            tj = np.interp(yaw_t, yaw[i0:i1 + 1][::-1] if yaw[i1] < yaw[i0] else yaw[i0:i1 + 1], t[i0:i1 + 1][::-1] if yaw[i1] < yaw[i0] else t[i0:i1 + 1]) + od[0, 0]
            k = int(np.argmin(np.abs(sc_t - tj))); sel = list(range(max(k - 2, 0), min(k + 3, len(sc)))); return sel, tj - od[0, 0]
        sels = [window(y) for y in targets]; first = [(sc[k][0] + 0.05 + R.DELTA, sc[k][2][::4]) for k in sels[0][0]]
        M, tree, nrm, ok = R.build_map(od, first)
        print("  (a3) LiDAR check, 5-scan windows placed with recorded poses, registered onto the first window (delta %.2f s). correction = what the pose chain is off by:" % R.DELTA)
        for (sel, tj), y in zip(sels, targets):
            Q = P.voxel(P.to_session_frame(od, [(sc[k][0] + 0.05 + R.DELTA, sc[k][2][::4]) for k in sel])); best = None
            for dyw in (0, 10, -10):
                T, inl, rms, rp = P.icp_plane(Q, tree, M, nrm, P.Tz(0, 0, dyw), ok=ok)
                if best is None or inl > best[1]: best = (T, inl)
            T, inl = best; print("       swept %+6.1f deg (t=%5.1f s): correction dx %+.3f dy %+.3f (%.3f m) dyaw %+.2f deg  inliers %.3f" % (y - yaw[i0], tj, T[0, 3], T[1, 3], math.hypot(T[0, 3], T[1, 3]), P.yaw_of(T), inl), flush=True)


def interp_pose(od):
    sl = Slerp(od[:, 0], Rotation.from_quat(od[:, 4:8])); return sl, od[:, 0], od[:, 1:4]


def place(od, sc, scans_idx, T_ext, delta, pts_stride=4):
    sl, to, po = interp_pose(od); out = []
    for k in scans_idx:
        s, toff, X = sc[k]; X, toff = X[::pts_stride], toff[::pts_stride]; r = np.linalg.norm(X, axis=1); m = (r > 0.5) & (r < RMAX)
        tq = np.clip(s + toff[m] + delta, to[0], to[-1]); Rm = sl(tq).as_matrix(); pos = np.stack([np.interp(tq, to, po[:, i]) for i in range(3)], 1)
        out.append(np.einsum("nij,nj->ni", Rm, X[m] + T_ext) + pos)
    return np.vstack(out)


def thickness(pts, cell=0.2, nmin=30, planar=0.6):
    """Per 0.2 m cell with >= 30 points: sqrt(smallest covariance eigenvalue). Wall = cell normal within 17 deg of horizontal. A tight planarity filter (0.2) hides
    smear (a smeared wall fails it), so the filter is loose (lambda1/lambda2 < 0.6) and the share of wall-like cells that pass the TIGHT filter is reported as well."""
    q = np.floor(pts / cell).astype(np.int64); _, inv = np.unique(q, axis=0, return_inverse=True); inv = inv.ravel(); n = np.bincount(inv)
    s1 = np.stack([np.bincount(inv, pts[:, i]) for i in range(3)], 1); s2 = np.stack([np.bincount(inv, pts[:, i] * pts[:, j]) for i in range(3) for j in range(3)], 1).reshape(-1, 3, 3)
    keep = n >= nmin; n, s1, s2 = n[keep], s1[keep], s2[keep]; mu = s1 / n[:, None]; cov = s2 / n[:, None, None] - mu[:, :, None] * mu[:, None, :]
    w, v = np.linalg.eigh(cov); ratio = w[:, 0] / np.maximum(w[:, 1], 1e-12); th = np.sqrt(np.maximum(w[:, 0], 0)); nz = np.abs(v[:, 2, 0])
    wall = (ratio < planar) & (nz < 0.3); flr = (ratio < planar) & (nz > 0.9); pl = ratio < planar
    tight = (ratio < 0.2) & (nz < 0.3)
    return np.median(th[wall]) * 1000, np.median(th[flr]) * 1000, np.median(th[pl]) * 1000, int(wall.sum()), tight.sum() / max(wall.sum(), 1)


def part_b():
    data = {k: load(v) for k, v in RUNS.items()}; idx = {}
    for name, (od, sc) in data.items():
        yaw = yaw_unwrapped(od); t = od[:, 0] - od[0, 0]; rate = np.gradient(yaw, t); mv = np.flatnonzero(np.abs(rate) > 5); lo, hi = t[mv[0]], t[mv[-1]]
        st = np.array([s - od[0, 0] for s, _, _ in sc]); ks = np.flatnonzero((st >= lo + 0.3) & (st <= hi - 0.3)); idx[name] = ks
        print("%s: %d scans inside the turn (%.1f to %.1f s)" % (name, len(ks), lo, hi))
    n = min(len(v) for v in idx.values()); sub = {k: v[np.linspace(0, len(v) - 1, 150).astype(int)] for k, v in idx.items()}
    print("150 scans per run (evenly spaced inside the turn), every 4th point, range 0.5-%.0f m, 0.2 m cells, >= 30 points, planar if lambda1/lambda2 < 0.2" % RMAX)
    print("thickness = sqrt(smallest covariance eigenvalue) in mm: wall cells / floor+ceiling cells / all planar cells (lambda1/lambda2 < 0.6); n = wall cells, tight = share of those passing lambda1/lambda2 < 0.2")
    print("delta = pose-time offset added to header stamp + point offset_time (0.15 = the pose-stamp lag of the route note)")
    best = {}
    for name in RUNS:
        od, sc = data[name]; print("-- %s, placed with its own extrinsic_T %s" % (name, T_USED[name])); rows = []
        for dl in np.arange(0.0, 0.351, 0.025):
            w, f, a, nw, nf = thickness(place(od, sc, sub[name], T_USED[name], dl)); rows.append((dl, w, f, a, nf)); print("   delta %.3f s: wall %.2f  floor/ceil %.2f  all %.2f  (n %d, tight %.2f)" % (dl, w, f, a, nw, nf), flush=True)
        r = np.array(rows); k = int(np.argmax(r[:, 4])); best[name] = r[k]; print("   sharpest by tight-planar share %.2f at delta %.3f s (wall %.2f mm); at delta 0.15: share %.2f wall %.2f mm; at 0: share %.2f wall %.2f mm" % (r[k, 4], r[k, 0], r[k, 1], r[6, 4], r[6, 1], r[0, 4], r[0, 1]))
    print("-- cross placement (the other run's extrinsic) at each run's best delta, sanity:")
    for name, other in (("corrected", "precorrection"), ("precorrection", "corrected")):
        od, sc = data[name]; w, f, a, nw, nf = thickness(place(od, sc, sub[name], T_USED[other], best[name][0])); print("   %s bag with %s T: wall %.2f floor/ceil %.2f all %.2f mm, tight share %.2f" % (name, other, w, f, a, nf))


if __name__ == "__main__":
    {"a": part_a, "b": part_b}[sys.argv[1] if len(sys.argv) > 1 else "a"]()
