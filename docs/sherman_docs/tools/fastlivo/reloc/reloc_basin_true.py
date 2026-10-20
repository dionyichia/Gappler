"""T3.5e A: basin of convergence around the corrected solution (the ICP-polished best of the y profile).
Starts are offsets from that solution; 'same' = within TOL_POS m and TOL_YAW deg of it. Run with LEVEL=1 GRAV4=1.
usage: reloc_basin_true.py MAP_BAG QUERY_BAG QUERY_SECONDS"""
import math, sys
import numpy as np
from scipy.spatial import cKDTree
import reloc_offline_prototype as P

map_bag, q_bag, qsec = sys.argv[1], sys.argv[2], float(sys.argv[3])
odom, scans = P.read(map_bag, scan_stride=2)
M = P.voxel(P.to_session_frame(odom, scans)); tree = cKDTree(M)
nrm, flat = P.normals(M, tree); ok = flat <= P.FLAT_MAX
qo, qs = P.read(q_bag, t_max=qsec); Q = P.voxel(P.to_session_frame(qo, qs))
T0, i0, _, rp0 = P.icp_plane(Q, tree, M, nrm, P.Tz(1.94, 1.19, 0), iters=80, ok=ok)
print('config LEVEL %d GRAV4 %s FLAT_MAX %g | reference solution: %s | inliers %.3f rms_pl %.3f' % (P.LEVEL, P.GRAV4, P.FLAT_MAX, P.pose_str(T0), i0, rp0))


def run(dx, dy, dyaw):
    a = math.radians(dyaw); Rz = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    init = T0.copy(); init[:3, 3] += (dx, dy, 0)
    R3 = np.eye(3); R3[:2, :2] = Rz; init[:3, :3] = R3 @ T0[:3, :3]
    T, inl, r2, rp = P.icp_plane(Q, tree, M, nrm, init, iters=80, ok=ok)
    dpos = np.linalg.norm(T[:3, 3] - T0[:3, 3]); dyw = (P.yaw_of(T) - P.yaw_of(T0) + 180) % 360 - 180
    return dpos < P.TOL_POS and abs(dyw) < P.TOL_YAW, dpos, dyw, inl
print('position offsets (8 directions, yaw offset 0): fraction returning to the reference')
for r in (0.3, 0.5, 1.0, 1.5, 2.0):
    res = [run(r * math.cos(t), r * math.sin(t), 0) for t in np.radians(np.arange(0, 360, 45))]
    print('  radius %.1f m: %d of 8 | worst dpos %.2f m' % (r, sum(x[0] for x in res), max(x[1] for x in res)))
print('yaw offsets (position offset 0):')
for d in (5, 10, 15, 20, 30, 45, 60):
    res = [run(0, 0, s * d) for s in (1, -1)]
    print('  +/-%d deg: %s' % (d, ' '.join('%s(%.2fm,%.1fdeg)' % ('same' if x[0] else 'DIFF', x[1], x[2]) for x in res)))
