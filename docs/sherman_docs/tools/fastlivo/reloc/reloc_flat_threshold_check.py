"""T3.5e: choose the planarity-filter default. For each FLAT_MAX: how much of the map is kept, how many kept normals are walls,
the self-test error (first 3 s of the map bag against its own map, must be ~0), and the query polished from the tape-measured start.
Run with LEVEL=1 GRAV4=1.  usage: reloc_flat_threshold_check.py MAP_BAG QUERY_BAG"""
import math, sys
import numpy as np
from scipy.spatial import cKDTree
import reloc_offline_prototype as P

map_bag, q_bag = sys.argv[1], sys.argv[2]
odom, scans = P.read(map_bag, scan_stride=2)
M = P.voxel(P.to_session_frame(odom, scans)); tree = cKDTree(M); nrm, flat = P.normals(M, tree)
so, ss = P.read(map_bag, t_max=3.0); S = P.voxel(P.to_session_frame(so, ss))
qo, qs = P.read(q_bag, t_max=3.0); Q = P.voxel(P.to_session_frame(qo, qs))
print('LEVEL %d GRAV4 %s | flat percentiles 10/50/90: %s' % (P.LEVEL, P.GRAV4, np.round(np.percentile(flat, [10, 50, 90]), 3)))
print('FLAT_MAX | kept  | walls(|nx|or|ny|>0.7) | self-test err (m, deg) | query polished from (2.0,1.2,0): pose | inliers | rms_pl | A^T A cond, weakest')
for thr in (0.1, 0.2, 0.3, 0.5, 1.0, 1e9):
    ok = flat <= thr
    Ts, i0, _, p0 = P.icp_plane(S, tree, M, nrm, P.Tz(0.3, -0.2, 10), ok=ok)
    T, inl, _, rp = P.icp_plane(Q, tree, M, nrm, P.Tz(2.0, 1.2, 0), ok=ok)
    p = Q @ T[:3, :3].T + T[:3, 3]; d, idx = tree.query(p); m = (d < 0.15) & ok[idx]
    n = nrm[idx[m]]; c = p[m].mean(0); A = np.hstack([np.cross(p[m] - c, n), n])[:, [2, 3, 4, 5]]
    w, v = np.linalg.eigh(A.T @ A / len(A))
    walls = ((abs(nrm[ok][:, 0]) > 0.7) | (abs(nrm[ok][:, 1]) > 0.7)).mean()
    print('%8g | %4.0f%% | %5.0f%% | %.3f m, %.2f deg | x %.3f y %.3f yaw %.2f | %.3f | %.3f | cond %.0f, %s %+.2f' % (
        thr, 100 * ok.mean(), 100 * walls, math.hypot(Ts[0, 3], Ts[1, 3]), P.yaw_of(Ts), T[0, 3], T[1, 3], P.yaw_of(T), inl, rp, w[-1] / w[0],
        ['yaw', 'tx', 'ty', 'tz'][int(np.argmax(abs(v[:, 0])))], v[int(np.argmax(abs(v[:, 0]))), 0]))
