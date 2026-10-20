"""T3.5e offline feasibility: register a fresh session's first seconds against a saved-style map.
Map and query are built from recorded LiDAR + mapper odometry (no robot, no mapper rerun).
usage: reloc_offline_prototype.py MAP_BAG QUERY_BAG [query_seconds]
env knobs (all default to the previous behaviour except FLAT_MAX):
  RMAX      max LiDAR range kept, m (40)
  MAP_T     build the map from only the first MAP_T seconds of MAP_BAG (unset = whole bag)
  GRAV4     1 = 4-DOF solve (yaw + x,y,z; roll/pitch fixed at the initial guess's 0)
  FLAT_MAX  drop map points whose normal is not planar: smallest/middle eigenvalue > FLAT_MAX (0.1; 1e9 = off)
  TOL_POS / TOL_YAW  'same answer' tolerance for the basin test, m / deg (0.10 / 4)
Only extrinsic_T is applied; extrinsic_R is identity in the mapper config."""
import math, os, sys
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from scipy.spatial import cKDTree

T_EXT = np.array([-0.011, -0.02329, 0.04412])  # extrinsic_T the mapper ran with (corrected value)
VOX = 0.10
RMAX = float(os.environ.get('RMAX', '40'))
MAP_T = float(os.environ['MAP_T']) if os.environ.get('MAP_T') else None
GRAV4 = os.environ.get('GRAV4') == '1'
FLAT_MAX = float(os.environ.get('FLAT_MAX', '0.1'))
TOL_POS = float(os.environ.get('TOL_POS', '0.10'))
TOL_YAW = float(os.environ.get('TOL_YAW', '4'))


def rot(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def read(bag, t_max=None, scan_stride=1, pt_stride=4):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='sqlite3'), rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=['/livox/lidar', '/aft_mapped_to_init']))
    odom, scans, t0, n = [], [], None, 0
    while r.has_next():
        topic, data, _ = r.read_next()
        m = deserialize_message(data, get_message(types[topic]))
        s = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        t0 = s if t0 is None else t0
        if t_max is not None and s - t0 > t_max:
            break
        if topic == '/aft_mapped_to_init':
            p, q = m.pose.pose.position, m.pose.pose.orientation
            odom.append((s, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
        else:
            n += 1
            if n % scan_stride:
                continue
            pts = np.array([(c.x, c.y, c.z) for c in m.points[::pt_stride]], dtype=np.float64)
            scans.append((s + 0.05, pts))
    return np.array(odom), scans


def first_poses(bag):
    """First /aft_mapped_to_init pose and its stamp relative to the first LiDAR message."""
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='sqlite3'), rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=['/livox/lidar', '/aft_mapped_to_init']))
    lid = od = None
    while r.has_next() and (lid is None or od is None):
        topic, data, _ = r.read_next()
        m = deserialize_message(data, get_message(types[topic]))
        s = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        if topic == '/livox/lidar' and lid is None:
            lid = s
        elif topic == '/aft_mapped_to_init' and od is None:
            p, q = m.pose.pose.position, m.pose.pose.orientation
            T = np.eye(4); T[:3, :3] = rot((q.x, q.y, q.z, q.w)); T[:3, 3] = (p.x, p.y, p.z)
            od = (s, T)
    return lid, od


def to_session_frame(odom, scans):
    ts = odom[:, 0]
    out = []
    for s, pts in scans:
        i = int(np.clip(np.searchsorted(ts, s), 1, len(ts) - 1))
        i = i if abs(ts[i] - s) < abs(ts[i-1] - s) else i - 1
        R, t = rot(odom[i, 4:8]), odom[i, 1:4]
        rng = np.linalg.norm(pts, axis=1)
        pts = pts[(rng > 0.5) & (rng < RMAX)]
        out.append((pts + T_EXT) @ R.T + t)
    return np.vstack(out)


def voxel(p, v=VOX):
    k = np.floor(p / v).astype(np.int64)
    _, idx = np.unique(k, axis=0, return_index=True)
    return p[idx]


def icp(src, tree, dst, init, iters=40, d0=1.0, d1=0.2):
    T = init.copy()
    for k in range(iters):
        d = d1 + (d0 - d1) * max(0.0, 1 - k / 20)
        p = src @ T[:3, :3].T + T[:3, 3]
        dist, idx = tree.query(p, distance_upper_bound=d)
        m = np.isfinite(dist)
        if m.sum() < 50:
            break
        A, B = p[m], dst[idx[m]]
        ca, cb = A.mean(0), B.mean(0)
        U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
        R = Vt.T @ U.T
        if np.linalg.det(R) < 0:
            Vt[-1] *= -1; R = Vt.T @ U.T
        dT = np.eye(4); dT[:3, :3] = R; dT[:3, 3] = cb - R @ ca
        T = dT @ T
    p = src @ T[:3, :3].T + T[:3, 3]
    dist, _ = tree.query(p)
    inl = dist < 0.15
    return T, inl.mean(), float(np.sqrt(np.mean(dist[inl] ** 2))) if inl.any() else float('nan')


def normals(M, tree, k=12):
    _, idx = tree.query(M, k=k)
    nb = M[idx]; nb = nb - nb.mean(1, keepdims=True)
    w, v = np.linalg.eigh(np.einsum('nki,nkj->nij', nb, nb))
    return v[:, :, 0], w[:, 0] / np.maximum(w[:, 1], 1e-9)


def icp_plane(src, tree, dst, nrm, init, iters=80, d0=1.0, d1=0.15, ok=None):
    """Point-to-plane ICP. ok: bool mask of usable (planar) map points. Returns T, inlier frac,
    point-to-point rms, point-to-plane rms (the latter is not capped by the voxel floor)."""
    T = init.copy()
    for k in range(iters):
        d = d1 + (d0 - d1) * max(0.0, 1 - k / 30)
        p = src @ T[:3, :3].T + T[:3, 3]
        dist, idx = tree.query(p, distance_upper_bound=d)
        m = np.isfinite(dist)
        if ok is not None:
            m &= ok[np.minimum(idx, len(dst) - 1)]
        if m.sum() < 100:
            break
        P, Q, N = p[m], dst[idx[m]], nrm[idx[m]]
        A = np.hstack([np.cross(P, N), N]); b = np.einsum('ij,ij->i', N, Q - P)
        if GRAV4:  # yaw about z only: keep column 2 of the rotation part, drop roll/pitch
            x = np.zeros(6); x[[2, 3, 4, 5]] = np.linalg.lstsq(A[:, [2, 3, 4, 5]], b, rcond=None)[0]
        else:
            x = np.linalg.lstsq(A, b, rcond=None)[0]
        a, t = x[:3], x[3:]
        R = np.eye(3) + np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
        U, _, Vt = np.linalg.svd(R); R = U @ Vt
        dT = np.eye(4); dT[:3, :3] = R; dT[:3, 3] = t
        T = dT @ T
    p = src @ T[:3, :3].T + T[:3, 3]
    dist, idx = tree.query(p)
    inl = dist < 0.15
    if not inl.any():
        return T, 0.0, float('nan'), float('nan')
    res = np.einsum('ij,ij->i', nrm[idx[inl]], p[inl] - dst[idx[inl]])
    return T, inl.mean(), float(np.sqrt(np.mean(dist[inl] ** 2))), float(np.sqrt(np.mean(res ** 2)))


def pose_str(T):
    yaw = math.degrees(math.atan2(T[1, 0], T[0, 0]))
    pitch = math.degrees(-math.asin(np.clip(T[2, 0], -1, 1)))
    roll = math.degrees(math.atan2(T[2, 1], T[2, 2]))
    return 'x %.3f y %.3f z %.3f m | yaw %.2f pitch %.2f roll %.2f deg' % (T[0, 3], T[1, 3], T[2, 3], yaw, pitch, roll)


def Tz(x, y, yawdeg):
    a = math.radians(yawdeg); T = np.eye(4)
    T[:2, :2] = [[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]; T[0, 3], T[1, 3] = x, y
    return T


def yaw_of(T):
    return math.degrees(math.atan2(T[1, 0], T[0, 0]))


if __name__ == '__main__':
    map_bag, q_bag = sys.argv[1], sys.argv[2]
    qsec = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    print('config: RMAX %g MAP_T %s GRAV4 %s FLAT_MAX %g tol %.2f m / %.1f deg' % (RMAX, MAP_T, GRAV4, FLAT_MAX, TOL_POS, TOL_YAW))
    for name, b in (('map bag', map_bag), ('query bag', q_bag)):
        lid, od = first_poses(b)
        T0 = od[1]
        print('ORIGIN %s: first odom pose x %.4f y %.4f z %.4f yaw %.3f deg (roll/pitch %s) at %+.3f s from first LiDAR msg' % (
            name, T0[0, 3], T0[1, 3], T0[2, 3], yaw_of(T0), pose_str(T0).split('|')[1].strip(), od[0] - lid))
    odom, scans = read(map_bag, t_max=MAP_T, scan_stride=2)
    M = voxel(to_session_frame(odom, scans)); tree = cKDTree(M)
    nrm, flat = normals(M, tree)
    ok = flat <= FLAT_MAX
    print('map: %d scans -> %d voxels (%.2f m), extent %s m; planar (flat<=%g): %d (%.0f%%)' % (len(scans), len(M), VOX, np.round(np.ptp(M, axis=0), 1), FLAT_MAX, ok.sum(), 100 * ok.mean()))
    qo, qs = read(q_bag, t_max=qsec)
    Q = voxel(to_session_frame(qo, qs))
    print('query: %d scans in first %.1f s -> %d voxels' % (len(qs), qsec, len(Q)))
    so, ss = read(map_bag, t_max=qsec)
    S = voxel(to_session_frame(so, ss))
    Ts, i0, r0, p0 = icp_plane(S, tree, M, nrm, Tz(0.3, -0.2, 10), ok=ok)
    print('SELF-TEST (map bag first %.0fs vs its own map, start offset 0.3,-0.2,10deg): %s | inliers %.2f rms_p2p %.3f rms_p2plane %.3f  (identity expected)' % (qsec, pose_str(Ts), i0, r0, p0))
    T, inl, rms, rmsp = icp_plane(Q, tree, M, nrm, np.eye(4), ok=ok)
    print('QUERY from identity: %s | inliers %.2f rms_p2p %.3f rms_p2plane %.3f m' % (pose_str(T), inl, rms, rmsp))
    base, n_ok = T, 0
    print('basin test (same = within %.2f m and %.1f deg of the identity-start answer):' % (TOL_POS, TOL_YAW))
    starts = [(0, 0, 0), (0.3, 0, 0), (0, 0.3, 0), (-0.3, -0.3, 0), (0, 0, 5), (0, 0, -5), (0, 0, 10), (0, 0, -10), (0, 0, 15), (0, 0, -15), (0, 0, 30), (0, 0, -30), (0.5, 0.5, 20), (-0.5, 0.5, -20), (0, 0, 60), (0, 0, 120), (0, 0, 180)]
    for dx, dy, dyaw in starts:
        Ti, i2, r2, p2 = icp_plane(Q, tree, M, nrm, Tz(dx, dy, dyaw), ok=ok)
        d = Ti[:3, 3] - base[:3, 3]; dyw = (yaw_of(Ti) - yaw_of(base) + 180) % 360 - 180
        same = np.linalg.norm(d) < TOL_POS and abs(dyw) < TOL_YAW; n_ok += same
        print('  init (%.1f,%.1f,%4d deg) -> %s | dpos %.3f m dyaw %.2f deg | inl %.2f rms_p2p %.3f rms_p2plane %.3f' % (dx, dy, dyaw, 'same' if same else 'DIFFERENT', np.linalg.norm(d), dyw, i2, r2, p2))
    print('same answer in %d of %d starts' % (n_ok, len(starts)))
    best = (0, None)
    for yaw in range(0, 360, 30):
        for dx, dy in [(0, 0), (0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5)]:
            Ti, i2, r2, p2 = icp_plane(Q, tree, M, nrm, Tz(dx, dy, yaw), iters=60, ok=ok)
            if i2 > best[0]: best = (i2, Ti, r2, p2)
    print('GLOBAL sweep (12 yaws x 5 offsets), best: %s | inliers %.2f rms_p2p %.3f rms_p2plane %.3f' % (pose_str(best[1]), best[0], best[2], best[3]))
