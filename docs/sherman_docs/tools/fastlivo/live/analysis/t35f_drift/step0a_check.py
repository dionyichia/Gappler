"""T3.5f drift step 0a check: is the run2-onto-run1 start answer unique, and does it fit the end-point swap?
(1) wide start grid for run2[0:3 s] -> run1[0:3 s], inliers per distinct answer.  (2) run2[0:3 s] -> run1[last 3 s] and run2[last 3 s] -> run1[0:3 s]
(each expected near identity if the runs share their end points).  Sensor-level, prototype settings (levelled, 4-DOF, FLAT_MAX 0.5)."""
import numpy as np
import drift_common as D
R, P = D.R, D.P


def win(label, lo, hi):
    odom, scans = R.read_fast(D.BAGS[label]); t0 = scans[0][0]; t1 = scans[-1][0] - t0
    if lo < 0: lo, hi = t1 + lo, t1 + hi
    sel = [sc for sc in scans if lo <= sc[0] - t0 <= hi]
    return odom, sel


def reg(qb, mb, label):
    om, sm = mb; oq, sq = qb
    M, tree, nrm, ok = R.build_map(om, sm); Q = P.voxel(P.to_session_frame(oq, sq)); out = []
    for dx, dy, dyaw in [(0, 0, 0)] + [(a, b, c) for a in (-1, -.5, 0, .5, 1) for b in (-1, -.5, 0, .5, 1) for c in (-20, 0, 20)]:
        T, inl, rms, rp = P.icp_plane(Q, tree, M, nrm, P.Tz(dx, dy, dyaw), ok=ok); out.append((inl, T))
    out.sort(key=lambda c: -c[0]); kept = []
    for inl, T in out:
        if all(np.linalg.norm(T[:2, 3] - t[:2, 3]) > 0.05 or abs(P.yaw_of(T) - P.yaw_of(t)) > 1 for _, t in kept): kept.append((inl, T))
    print(label)
    for inl, T in kept[:4]:
        print("   dx %+.3f dy %+.3f dyaw %+.2f deg  inliers %.3f" % (T[0, 3], T[1, 3], P.yaw_of(T), inl))


r1a, r1z, r2a, r2z = win("run1", 0, 3), win("run1", -3, 0), win("run2", 0, 3), win("run2", -3, 0)
reg(r2a, r1a, "run2[0:3 s]  -> run1[0:3 s]   (step 0a; 81 starts, distinct answers)")
reg(r2a, r1z, "run2[0:3 s]  -> run1[last 3 s]  (identity if run 2 starts where run 1 ended)")
reg(r2z, r1a, "run2[last 3 s] -> run1[0:3 s]   (identity if run 2 ends where run 1 started)")
reg(r1z, r1a, "run1[last 3 s] -> run1[0:3 s]   (closure, scan-to-scan; compare start_end_check)")
