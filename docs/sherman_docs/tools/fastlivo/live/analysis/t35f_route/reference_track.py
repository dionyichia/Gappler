"""T3.5f route analysis 2: an independent reference track for a run, from registration against another session's map with the frozen T3.5e prototype
(reloc_offline_prototype.py: levelled sessions, 4-DOF yaw+xyz point-to-plane, planar map points only FLAT_MAX 0.5, voxel 0.10, inlier radius 0.15 m).
Map = MAP_BAG built from its own mapper poses. Query = QUERY_BAG, 1 s windows every 3 s, each window placed with the query's own poses, then registered to
the map. Window i starts from the previous accepted window's solution. A window is dropped if its inlier fraction is below the 0.9 gate.
T_win(t) maps the query's levelled session frame into the map frame. If the query's odometry did not drift, T_win would be constant, so
  error(t) = T_win(first) p_fl(t) - T_win(t) p_fl(t)      (FAST-LIVO2 position minus the reference position, in the map frame)
is the drift the reference sees, zero at the first accepted window by construction.
usage: reference_track.py OUT_PREFIX MAP_BAG LABEL=QUERY_BAG [...]    -> OUT_PREFIX_LABEL.csv"""
import csv, math, sys
import numpy as np
import route_common as R
P = R.P
WIN, STEP, GATE = 1.0, 3.0, 0.9
COLS = ["t_s", "path_m", "fl_x", "fl_y", "ref_x", "ref_y", "err_x", "err_y", "err_h", "err_z", "dyaw_deg", "inliers", "rms_plane", "accepted", "Twin_x", "Twin_y", "Twin_yaw"]

omap, smap = R.read_fast(sys.argv[2], scan_stride=2)
M, tree, nrm, ok = R.build_map(omap, smap)
print("map: %d voxels (%d planar) from %s" % (len(M), ok.sum(), sys.argv[2]))
for arg in sys.argv[3:]:
    label, bag = arg.split("=", 1)
    odom, scans = R.read_fast(bag)
    pos, _ = R.session_track(odom)
    path = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pos[:, :2], axis=0).T))])
    t0 = odom[0, 0]; stamps = np.array([s for s, _ in scans]); rows = []; T_prev = None; T_first = None
    for ts in np.arange(0, stamps[-1] - t0 - WIN + 1e-6, STEP):
        sel = [k for k in range(len(scans)) if ts <= stamps[k] - t0 < ts + WIN]
        if len(sel) < 5:
            continue
        Q = P.voxel(P.to_session_frame(odom, [scans[k] for k in sel]))
        if T_prev is None:  # first window: identity first, then a coarse grid, best inlier fraction wins
            best = None
            for dx, dy, dyaw in [(0, 0, 0)] + [(a, b, c) for a in (-1.5, -1, -.5, 0, .5, 1, 1.5) for b in (-1.5, -1, -.5, 0, .5, 1, 1.5) for c in (-30, -15, 0, 15, 30)]:
                T, inl, rms, rp = P.icp_plane(Q, tree, M, nrm, P.Tz(dx, dy, dyaw), ok=ok)
                if best is None or inl > best[1]:
                    best = (T, inl, rms, rp)
                if dx == dy == dyaw == 0 and inl >= GATE:
                    break
            T, inl, rms, rp = best
        else:
            T, inl, rms, rp = P.icp_plane(Q, tree, M, nrm, T_prev, ok=ok)
        passed = inl >= GATE
        if passed:
            T_prev = T
            T_first = T if T_first is None else T_first
        tc = float(np.mean(stamps[sel])); j = int(np.clip(np.searchsorted(odom[:, 0], tc), 0, len(odom) - 1))
        p = np.append(pos[j], 1.0)
        if T_first is None:
            rows.append([tc - t0, path[j], *pos[j, :2], np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, inl, rp, 0, T[0, 3], T[1, 3], P.yaw_of(T)]); continue
        ref, fl = (T @ p)[:3], (T_first @ p)[:3]; e = fl - ref
        rows.append([tc - t0, path[j], *fl[:2], *ref[:2], e[0], e[1], math.hypot(e[0], e[1]), e[2], (P.yaw_of(T_first) - P.yaw_of(T) + 180) % 360 - 180,
                     inl, rp, int(passed), T[0, 3], T[1, 3], P.yaw_of(T)])
        if not passed:
            rows[-1][5:11] = [np.nan] * 6
        print("  %s t=%5.1f s path %5.2f m  inl %.3f rms_pl %.3f  %s  err_h %.3f m dyaw %+.2f" % (label, rows[-1][0], path[j], inl, rp, "ok  " if passed else "DROP", rows[-1][8], rows[-1][10]), flush=True)
    with open("%s_%s.csv" % (sys.argv[1], label), "w", newline="") as f:
        w = csv.writer(f); w.writerow(COLS); w.writerows(rows)
    a = np.array(rows, dtype=float); acc = a[:, 13] == 1
    print("%s: %d windows, %d accepted (gate %.1f), dropped %d; last accepted error %.3f m horizontal, %+.3f m z, %+.2f deg" % (
        label, len(a), acc.sum(), GATE, (~acc).sum(), a[acc][-1, 8], a[acc][-1, 9], a[acc][-1, 10]))
