"""T3.5f closure independence check. No map, no odometry in the fit: registers 3 s cloud windows of the raw LiDAR scans in the sensor frame
(6-DOF point-to-plane, frozen prototype icp_plane, GRAV4 off, planar targets, range 0.5..RMAX).
Part 1, per run: last 3 s (source) onto first 3 s (target) from (a) IDENTITY ("came back") and (b) the ODOMETRY answer. Each start is also scored with no
optimisation (iters=0), so "the fit at zero displacement" is a number, not an assumption.  Closure = odometry end-start minus LiDAR-only end-start.
Part 2, cross-run (robot not moved between runs): run 2 first 3 s onto run 1 last 3 s, and run 2 last 3 s onto run 1 first 3 s, from identity
and from a ring of 8 starts 0.5 m out (basin check).  If P/Q swapped, both are ~identity.
usage: closure_independence.py SECONDS RMAX LABEL=BAG_DIR LABEL=BAG_DIR   (labels run1 and run2)"""
import math, sys
import numpy as np
from scipy.spatial import cKDTree
import route_common as R
P = R.P
P.GRAV4 = False
sec, rmax = float(sys.argv[1]), float(sys.argv[2])
bags = dict(a.split("=", 1) for a in sys.argv[3:])


def cloud(scans, lo, hi, t0):
    sel = [(s, p) for s, p in scans if lo <= s - t0 <= hi]
    X = np.vstack([p for _, p in sel]); r = np.linalg.norm(X, axis=1)
    return P.voxel(X[(r > 0.5) & (r < rmax)]), sel[0][0], sel[-1][0], len(sel)


def target(C):
    tree = cKDTree(C); nrm, flat = P.normals(C, tree)
    return tree, nrm, flat <= P.FLAT_MAX


def fmt(T):
    return "x %+.3f y %+.3f z %+.3f (horizontal %.3f) yaw %+.2f deg" % (T[0, 3], T[1, 3], T[2, 3], math.hypot(T[0, 3], T[1, 3]), P.yaw_of(T))


def fit(tag, src, tgt, init):
    tree, nrm, ok = tgt; C = tgt_cloud[id(tgt)]
    T0, i0, r0, rp0 = P.icp_plane(src, tree, C, nrm, init, iters=0, ok=ok)
    T, inl, rms, rp = P.icp_plane(src, tree, C, nrm, init, ok=ok)
    print("   %-22s start %s\n   %-22s   unoptimised: inliers %.3f rms_plane %.3f | converged: %s | inliers %.3f rms_plane %.3f" % (
        tag, fmt(init), "", i0, rp0, fmt(T), inl, rp), flush=True)
    return T, inl


tgt_cloud = {}
W = {}
for label, bag in bags.items():
    odom, scans = R.read_fast(bag)
    t0 = scans[0][0]; t1 = scans[-1][0] - t0
    first = cloud(scans, 0, sec, t0); last = cloud(scans, t1 - sec, t1, t0)
    W[label] = dict(odom=odom, first=first, last=last)
    for k in ("first", "last"):
        c = W[label][k]; j0 = int(np.searchsorted(odom[:, 0], c[1])); j1 = int(np.searchsorted(odom[:, 0], c[2]))
        seg = odom[j0:j1 + 1, 1:4]
        W[label][k + "_move"] = float(np.max(np.linalg.norm(seg[:, :2] - seg[:, :2].mean(0), axis=1)))  # max excursion; summed step length would count jitter
        W[label][k + "_j"] = (j0, int(np.clip(j1, 0, len(odom) - 1)))
    print("%s: window %.0f s | first %d scans %d voxels, odom max excursion inside window %.3f m | last %d scans %d voxels, excursion %.3f m" % (
        label, sec, first[3], len(first[0]), W[label]["first_move"], last[3], len(last[0]), W[label]["last_move"]), flush=True)


def tg(label, k):
    t = target(W[label][k][0]); tgt_cloud[id(t)] = W[label][k][0]; W[label][k + "_tgt"] = t; return t


print("\n=== Part 1: within a run, last %.0f s onto first %.0f s (sensor frame) ===" % (sec, sec))
res1 = {}
for label in sorted(bags):
    w = W[label]; odom = w["odom"]; j0 = w["first_j"][0]; j1 = w["last_j"][1]
    R0 = P.rot(odom[j0, 4:8]); d = R0.T @ (odom[j1, 1:4] - odom[j0, 1:4]); Rrel = R0.T @ P.rot(odom[j1, 4:8])
    To = np.eye(4); To[:3, :3] = Rrel; To[:3, 3] = d
    print("%s: odometry first-to-last (window edges, first window start to last window end): %s" % (label, fmt(To)))
    t = tg(label, "first"); src = w["last"][0]
    Ti, inl_i = fit("from IDENTITY", src, t, np.eye(4))
    Tp, inl_p = fit("from ODOMETRY", src, t, To)
    print("   identity-start vs odometry-start converged: %.3f m apart, %.2f deg" % (np.linalg.norm(Ti[:3, 3] - Tp[:3, 3]), (P.yaw_of(Ti) - P.yaw_of(Tp) + 180) % 360 - 180))
    L = Tp if inl_p >= inl_i else Ti
    dd = To[:3, 3] - L[:3, 3]
    print("   CLOSURE (odometry minus LiDAR-only, better fit): x %+.3f y %+.3f z %+.3f m, horizontal %.3f m, yaw %+.2f deg\n" % (
        dd[0], dd[1], dd[2], math.hypot(dd[0], dd[1]), P.yaw_of(To) - P.yaw_of(L)))
    res1[label] = L

print("=== Part 2: cross-run, robot not moved between runs ===")
ring = [(0.5 * math.cos(a), 0.5 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
for src_l, src_k, dst_l, dst_k, name in (("run2", "first", "run1", "last", "run 2 first %.0f s onto run 1 last %.0f s" % (sec, sec)),
                                         ("run2", "last", "run1", "first", "run 2 last %.0f s onto run 1 first %.0f s" % (sec, sec))):
    print(name)
    t = tg(dst_l, dst_k); src = W[src_l][src_k][0]
    Ti, inl = fit("from IDENTITY", src, t, np.eye(4))
    out = []
    for dx, dy in ring:
        Tr, ir, _, _ = P.icp_plane(src, t[0], tgt_cloud[id(t)], t[1], P.Tz(dx, dy, 0), ok=t[2]); out.append((Tr, ir))
    best = max(out, key=lambda o: o[1])
    spread = max(np.linalg.norm(o[0][:3, 3] - Ti[:3, 3]) for o in out)
    print("   ring of 8 starts 0.5 m out: inliers %.3f..%.3f, worst distance of a converged fit from the identity-start fit %.3f m, best-inlier fit: %s\n" % (
        min(o[1] for o in out), max(o[1] for o in out), spread, fmt(best[0])), flush=True)
