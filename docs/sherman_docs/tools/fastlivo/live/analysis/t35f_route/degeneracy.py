"""T3.5f route analysis 1: does the route have a weak direction? Per scan (every 5th), normals of the session's own accumulated map at the scan's
points, then eigenvalues of the translation information matrix H = mean(n n^T) over matched planar points (trace 1, so a value is a share of the
information, not a count). Also the horizontal 2x2 block and a 4-DOF (yaw about the robot, x, y, z) version. Each is computed twice: all points,
and only points inside the glass box (the points that survive replay C).
usage: degeneracy.py OUT_PREFIX LABEL=BAG_DIR [...]   -> OUT_PREFIX_LABEL.csv"""
import csv, sys
import numpy as np
import route_common as R
P = R.P

COLS = ["t_s", "x", "y", "yaw_deg", "glass_dist_m", "n_all", "lam3_min", "lam3_mid", "lam3_max", "weak3_x", "weak3_y", "weak3_z",
        "lam2_min", "weak2_deg", "lam4_min", "n_in", "lam3_min_in", "lam2_min_in", "weak2_deg_in", "lam4_min_in"]


def info(p, n, pos):
    """p, n: matched points and their unit normals (session frame); pos: robot position. Returns lam3, vec3, lam2, ang2, lam4min."""
    H = n.T @ n / len(n)
    w3, v3 = np.linalg.eigh(H)
    w2, v2 = np.linalg.eigh(H[:2, :2])
    A = np.hstack([np.cross(p - pos, n)[:, 2:3], n])
    w4 = np.linalg.eigvalsh(A.T @ A / len(A))
    return w3, v3[:, 0], w2[0], np.degrees(np.arctan2(v2[1, 0], v2[0, 0])) % 180, w4[0]


for arg in sys.argv[2:]:
    label, bag = arg.split("=", 1)
    odom, scans = R.read_fast(bag, scan_stride=1)
    M, tree, nrm, ok = R.build_map(odom, scans[::2])  # frozen recipe: every 2nd scan builds the map
    pos, yaw = R.session_track(odom)
    rows = []
    for k in range(0, len(scans), 5):
        s, pts = scans[k]
        q = P.to_session_frame(odom, [(s, pts)])
        d, i = tree.query(q, distance_upper_bound=0.15)
        m = np.isfinite(d); m[m] &= ok[i[m]]
        if m.sum() < 200:
            continue
        j = int(np.clip(np.searchsorted(odom[:, 0], s), 0, len(odom) - 1))
        pp, nn = q[m], nrm[i[m]]
        w3, v3, w2, a2, w4 = info(pp, nn, pos[j])
        ins = (pp[:, 0] >= R.BOX[0]) & (pp[:, 0] <= R.BOX[1]) & (pp[:, 1] >= R.BOX[2]) & (pp[:, 1] <= R.BOX[3])
        if ins.sum() >= 200:
            w3i, _, w2i, a2i, w4i = info(pp[ins], nn[ins], pos[j])
        else:
            w3i, w2i, a2i, w4i = [np.nan] * 4
        rows.append([s - odom[0, 0], pos[j, 0], pos[j, 1], yaw[j], R.glass_distance(pos[j:j + 1, :2])[0], int(m.sum()), w3[0], w3[1], w3[2], *v3,
                     w2, a2, w4, int(ins.sum()), w3i[0] if ins.sum() >= 200 else np.nan, w2i, a2i, w4i])
    with open("%s_%s.csv" % (sys.argv[1], label), "w", newline="") as f:
        w = csv.writer(f); w.writerow(COLS); w.writerows(rows)
    a = np.array(rows)
    print("%s: %d scans analysed of %d, map %d voxels (%d planar). lam3_min median %.4f p10 %.4f min %.4f | lam2_min median %.4f p10 %.4f | in-box lam3_min median %.4f" % (
        label, len(a), len(scans), len(M), ok.sum(), np.median(a[:, 6]), np.percentile(a[:, 6], 10), a[:, 6].min(), np.median(a[:, 12]), np.percentile(a[:, 12], 10), np.nanmedian(a[:, 16])))
