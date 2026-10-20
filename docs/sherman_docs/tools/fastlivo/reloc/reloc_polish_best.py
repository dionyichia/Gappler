"""T3.5e A: the y profile fixes the query CENTROID's y, the sweep reports the query ORIGIN. Convert the profile's best rows to origin poses
(t = c_map - R c0), polish with ICP, and compare with the sweep's best. Run with LEVEL=1 GRAV4=1 (FLAT_MAX as wanted).
usage: reloc_polish_best.py MAP_BAG QUERY_BAG QUERY_SECONDS CSV"""
import csv, math, sys
import numpy as np
from scipy.spatial import cKDTree
import reloc_offline_prototype as P

map_bag, q_bag, qsec, csvp = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
odom, scans = P.read(map_bag, scan_stride=2)
M = P.voxel(P.to_session_frame(odom, scans)); tree = cKDTree(M)
nrm, flat = P.normals(M, tree); ok = flat <= P.FLAT_MAX
qo, qs = P.read(q_bag, t_max=qsec); Q = P.voxel(P.to_session_frame(qo, qs)); c0 = Q.mean(0)
print('config LEVEL %d GRAV4 %s FLAT_MAX %g | query %.0f s centroid in query frame: x %.2f y %.2f z %.2f' % (P.LEVEL, P.GRAV4, P.FLAT_MAX, qsec, *c0))
rows = sorted(csv.DictReader(open(csvp)), key=lambda d: -float(d['inliers']))[:3]
seen = []
for d in rows:
    y, x, yaw = float(d['y_m']), float(d['x_m']), float(d['yaw_deg'])
    a = math.radians(yaw); R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    t = np.array([x, y]) - R @ c0[:2]
    T0 = P.Tz(t[0], t[1], yaw)
    T, inl, r2, rp = P.icp_plane(Q, tree, M, nrm, T0, iters=80, ok=ok)
    print('profile row y %.1f (centroid x %.2f yaw %.1f, inl %.3f) -> origin pose x %.3f y %.3f yaw %.2f; ICP-polished: %s | inliers %.3f rms_p2p %.3f rms_pl %.3f' % (y, x, yaw, float(d['inliers']), t[0], t[1], yaw, P.pose_str(T), inl, r2, rp))
    seen.append((inl, T))
inl, T = max(seen, key=lambda s: s[0])
p = Q @ T[:3, :3].T + T[:3, 3]; dist, idx = tree.query(p); m = (dist < 0.15) & ok[idx]
n = nrm[idx[m]]; c = p[m].mean(0); A = np.hstack([np.cross(p[m] - c, n), n])[:, [2, 3, 4, 5]]
w, v = np.linalg.eigh(A.T @ A / len(A))
print('A^T A 4-DOF at polished best (N=%d): eigenvalues %s condition %.1f; weakest: %s' % (len(A), np.array2string(w, precision=3), w[-1] / w[0], ', '.join('%s %+.2f' % (['yaw', 'tx', 'ty', 'tz'][i], v[i, 0]) for i in np.argsort(-abs(v[:, 0]))[:3])))
print('normals among planar inliers: |nx|>0.7 %.0f%% |ny|>0.7 %.0f%% |nz|>0.7 %.0f%%' % tuple(100 * (abs(n[:, k]) > 0.7).mean() for k in range(3)))
