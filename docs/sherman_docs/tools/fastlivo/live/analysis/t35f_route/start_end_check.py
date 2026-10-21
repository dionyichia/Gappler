"""T3.5f route analysis 2b: did the robot physically end where it started? Register the LAST scans of a bag directly onto the FIRST scans, in the sensor
frame, with no odometry and no map. Both ends are (nearly) stationary, so each cloud is a clean snapshot of the room from one pose.
The result is the end pose relative to the start pose as the LiDAR itself sees it. Compare with the odometry's own first-to-last difference
expressed in the start frame. 6-DOF point-to-plane (the frozen prototype's icp_plane with GRAV4 off), planar targets only, range < RMAX_SE.
usage: start_end_check.py SECONDS RMAX_SE LABEL=BAG_DIR [...]"""
import math, sys
import numpy as np
from scipy.spatial import cKDTree
import route_common as R
P = R.P
P.GRAV4 = False

sec, rmax = float(sys.argv[1]), float(sys.argv[2])


def cloud(scans, lo, hi, t0):
    pts = [p for s, p in scans if lo <= s - t0 <= hi]
    X = np.vstack(pts); r = np.linalg.norm(X, axis=1)
    return P.voxel(X[(r > 0.5) & (r < rmax)]), len(pts)


for arg in sys.argv[3:]:
    label, bag = arg.split("=", 1)
    odom, scans = R.read_fast(bag)
    t0 = scans[0][0]; t1 = scans[-1][0] - t0
    A, na = cloud(scans, 0, sec, t0); B, nb = cloud(scans, t1 - sec, t1, t0)
    tree = cKDTree(A); nrm, flat = P.normals(A, tree); ok = flat <= P.FLAT_MAX
    best = None
    for yaw in (0, 5, -5):
        T, inl, rms, rp = P.icp_plane(B, tree, A, nrm, P.Tz(0, 0, yaw), ok=ok)
        if best is None or inl > best[1]:
            best = (T, inl, rp)
    T, inl, rp = best
    # odometry's own claim, in the start sensor frame (levelled frames differ by < 1 deg; horizontal numbers only)
    j0 = int(np.searchsorted(odom[:, 0], scans[0][0])); j1 = int(np.clip(np.searchsorted(odom[:, 0], scans[-1][0]), 0, len(odom) - 1))
    R0 = P.rot(odom[j0, 4:8]); d = R0.T @ (odom[j1, 1:4] - odom[j0, 1:4]); Rrel = R0.T @ P.rot(odom[j1, 4:8])
    yaw_odom = math.degrees(math.atan2(Rrel[1, 0], Rrel[0, 0]))
    sp = np.hypot(*(odom[j1, 1:3] - odom[max(j1 - 20, 0), 1:3])) / 1.0
    print("%s: first/last %.1f s (%d / %d scans, %d / %d voxels), end-of-bag speed %.3f m/s" % (label, sec, na, nb, len(A), len(B), sp))
    print("   LiDAR scan-to-scan: end pose in start frame x %+.3f y %+.3f z %+.3f m (horizontal %.3f), yaw %+.2f deg | inliers %.3f rms_plane %.3f" % (
        T[0, 3], T[1, 3], T[2, 3], math.hypot(T[0, 3], T[1, 3]), P.yaw_of(T), inl, rp))
    print("   odometry first-to-last in the same frame: x %+.3f y %+.3f z %+.3f m (horizontal %.3f), yaw %+.2f deg" % (d[0], d[1], d[2], math.hypot(d[0], d[1]), yaw_odom))
    print("   difference (odometry minus LiDAR): x %+.3f y %+.3f m (horizontal %.3f), yaw %+.2f deg" % (d[0] - T[0, 3], d[1] - T[1, 3], math.hypot(d[0] - T[0, 3], d[1] - T[1, 3]), yaw_odom - P.yaw_of(T)))
