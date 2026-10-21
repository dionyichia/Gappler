"""T3.5f drift step 3: along the route. Every 1 s window (1 s step) of run 1 and run 2 is placed with the run's own poses, then registered onto the handdriven1
map with the frozen T3.5e prototype (levelled, 4-DOF, FLAT_MAX 0.5, voxel 0.10, gate 0.9). Initial guess for EVERY window = the run's own pose after the
step 0 frame offset, inv(F_hd1) @ F_run (no chaining from the previous window), so a failed window cannot poison the next one.
error = FAST-LIVO2 minus reference, in the run 1 frame (reference = handdriven1 map, carrying ~7 cm of its own error). Also yaw error and the
along-track decomposition. T35_DELTA (env) is the scan-stamp convention: 0 = prototype, 0.15 = the pose-stamp lag found in the route note.
usage: T35_DELTA=0.15 step3.py"""
import csv, math, os
import numpy as np
from scipy.spatial import cKDTree
import drift_common as D
R, P = D.R, D.P
GATE, WIN, STEP = 0.9, 1.0, 1.0
frames = D.load_frames(); Fh_inv = D.tf_inv(frames["hd1"])
oh, sh = R.read_fast(D.BAGS["hd1"], scan_stride=2)
Mh, treeh, nh, okh = R.build_map(oh, sh)
floor = -0.148   # step12_info.json floor_z of hd1
band = Mh[(Mh[:, 2] - floor >= 0.2) & (Mh[:, 2] - floor <= 1.5)]; bandtree = cKDTree(band[:, :2])
tag = "d%03d" % round(R.DELTA * 100)
COLS = ["t_s", "path_m", "x1", "y1", "speed", "yawrate_dps", "glass_dist", "wall_dist", "inliers", "accepted", "ex", "ey", "eh", "ez", "e_along", "e_cross", "dyaw_deg"]
for lab in ("run1", "run2"):
    odom, scans = R.read_fast(D.BAGS[lab]); pos, yaw = R.session_track(odom)
    t0 = odom[0, 0]; stamps = np.array([s for s, _ in scans]); path = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pos[:, :2], axis=0).T))])
    Tinit = Fh_inv @ frames[lab]; Rr = frames["hd1"][:3, :3]; rows = []; nd = 0
    for ts in np.arange(0, stamps[-1] - t0 - WIN + 1e-6, STEP):
        sel = [k for k in range(len(scans)) if ts <= stamps[k] - t0 < ts + WIN]
        if len(sel) < 5:
            continue
        Q = P.voxel(P.to_session_frame(odom, [scans[k] for k in sel]))
        T, inl, rms, rp = P.icp_plane(Q, treeh, Mh, nh, Tinit, ok=okh)
        tc = float(np.mean(stamps[sel])); j = int(np.clip(np.searchsorted(odom[:, 0], tc), 1, len(odom) - 2))
        v = (pos[j + 1, :2] - pos[j - 1, :2]) / (odom[j + 1, 0] - odom[j - 1, 0]); spd = float(np.hypot(*v))
        yr = float(((yaw[j + 1] - yaw[j - 1] + 180) % 360 - 180) / (odom[j + 1, 0] - odom[j - 1, 0]))
        p = np.append(pos[j], 1.0); ph = Tinit @ p; p1 = D.apply(frames[lab], pos[j:j + 1])[0]
        ok = inl >= GATE
        e = Rr @ (ph[:3] - (T @ p)[:3]) if ok else np.full(3, np.nan)
        dy = (P.yaw_of(Tinit) - P.yaw_of(T) + 180) % 360 - 180 if ok else np.nan
        u = np.array([v[0], v[1]]) / max(spd, 1e-6); alo = e[0] * u[0] + e[1] * u[1]; cr = -e[0] * u[1] + e[1] * u[0]
        nd += (not ok)
        rows.append([tc - t0, path[j], p1[0], p1[1], spd, yr, R.glass_distance(p1[None, :2])[0], bandtree.query(ph[None, :2])[0][0], inl, int(ok), e[0], e[1], math.hypot(e[0], e[1]) if ok else np.nan, e[2], alo, cr, dy])
    with open("%s/step3_%s_%s.csv" % (D.OUT, lab, tag), "w", newline="") as f:
        w = csv.writer(f); w.writerow(COLS); w.writerows(rows)
    a = np.array(rows, float); acc = a[:, 9] == 1
    print("%s DELTA=%.2f: %d windows, %d accepted at gate %.1f, %d dropped; error vs handdriven1 reference: median %.3f m, p90 %.3f, max %.3f at t=%.0f s; end (last 5 accepted) mean %.3f m" % (
        lab, R.DELTA, len(a), acc.sum(), GATE, nd, np.nanmedian(a[:, 12]), np.nanpercentile(a[:, 12], 90), np.nanmax(a[:, 12]), a[np.nanargmax(a[:, 12]), 0], np.nanmean(a[acc][-5:, 12])))
    print("   inliers min %.3f median %.3f ; |e_along|/|e_cross| medians %.3f / %.3f ; first window error %.3f m" % (a[:, 8].min(), np.median(a[:, 8]), np.nanmedian(np.abs(a[:, 14])), np.nanmedian(np.abs(a[:, 15])), a[0, 12]), flush=True)
