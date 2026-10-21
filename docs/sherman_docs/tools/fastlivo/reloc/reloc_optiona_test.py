"""T3.5e option-A test: an operator-style guess near the tape-measured start, perturbed to the corners of +/-0.5 m and +/-15 deg (8 starts).
Reports how many converge to the reference solution and how many also pass the inlier-fraction gate (GATE, default 0.9).
Run with LEVEL=1 GRAV4=1.  usage: reloc_optiona_test.py MAP_BAG QUERY_BAG"""
import itertools, math, os, sys
import numpy as np
from scipy.spatial import cKDTree
import reloc_offline_prototype as P

GATE = float(os.environ.get('GATE', '0.9'))
map_bag, q_bag = sys.argv[1], sys.argv[2]
odom, scans = P.read(map_bag, scan_stride=2)
M = P.voxel(P.to_session_frame(odom, scans)); tree = cKDTree(M); nrm, flat = P.normals(M, tree); ok = flat <= P.FLAT_MAX
qo, qs = P.read(q_bag, t_max=3.0); Q = P.voxel(P.to_session_frame(qo, qs))
T0, i0, _, rp0 = P.icp_plane(Q, tree, M, nrm, P.Tz(1.94, 1.19, 0), iters=80, ok=ok)
print('config LEVEL %d GRAV4 %s FLAT_MAX %g | reference (polished from 1.94, 1.19, 0): %s | inliers %.3f rms_pl %.3f | gate %.2f' % (P.LEVEL, P.GRAV4, P.FLAT_MAX, P.pose_str(T0), i0, rp0, GATE))
conv = gate = both = 0
for sx, sy, sa in itertools.product((-1, 1), repeat=3):
    T, inl, _, rp = P.icp_plane(Q, tree, M, nrm, P.Tz(2.0 + 0.5 * sx, 1.2 + 0.5 * sy, 15 * sa), iters=80, ok=ok)
    dpos = np.linalg.norm(T[:3, 3] - T0[:3, 3]); dyw = (P.yaw_of(T) - P.yaw_of(T0) + 180) % 360 - 180
    c = dpos < P.TOL_POS and abs(dyw) < P.TOL_YAW; g = inl >= GATE; conv += c; gate += g; both += c and g
    print('  start (%.1f, %.1f, %+3d deg) -> x %.3f y %.3f yaw %+.2f | dpos %.3f m dyaw %+.2f deg | inliers %.3f rms_pl %.3f | %s | gate %s' % (
        2.0 + 0.5 * sx, 1.2 + 0.5 * sy, 15 * sa, T[0, 3], T[1, 3], P.yaw_of(T), dpos, dyw, inl, rp, 'CONVERGED' if c else 'different', 'PASS' if g else 'FAIL'))
print('converged to the reference: %d of 8 | pass the gate: %d of 8 | converged and passed: %d of 8' % (conv, gate, both))
