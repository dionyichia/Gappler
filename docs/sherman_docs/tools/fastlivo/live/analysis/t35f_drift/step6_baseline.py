"""T3.5f drift step 6: stationary baseline. The stationary bags carry no mapper poses (raw capture only), so the drift is read at sensor level:
LiDAR first 1 s vs last 1 s registered scan-to-scan in the sensor frame (6-DOF point-to-plane, frozen prototype settings, no odometry, no map).
A moving platform is not involved, so any displacement is sensor range/scene change, NOT estimator drift. Also the IMU gyro bias per bag (mean of the still part)
and the yaw a bias-uncorrected integration would give. Moving bags: gyro bias from their first 3 s (before the push).
usage: step6_baseline.py"""
import glob, math, sqlite3
import numpy as np
from scipy.spatial import cKDTree
import drift_common as D
R, P = D.R, D.P
P.GRAV4 = False
L = D.L
STAT = {"t35b_proof2 (Oct 17)": L + "/t35b-capture.R0fVks/t35b_proof2", "t35b_proof3 (Oct 17)": L + "/t35b-capture.R0fVks/t35b_proof3",
        "stationary01 (Oct 19)": L + "/t35c-capture-20261019.of23agzq/stationary01", "stationary02 (Oct 19)": L + "/t35c-capture-20261019.of23agzq/stationary02"}
MOVE = {"handdriven1 (Oct 20)": D.BAGS["hd1"], "spin-corrected (Oct 20)": L + "/t35d-attended-20261020.raLTgE/spin-corrected/bag",
        "run1 (Oct 21)": D.BAGS["run1"], "run2 (Oct 21)": D.BAGS["run2"]}


def imu(bag):
    from rclpy.serialization import deserialize_message
    from sensor_msgs.msg import Imu
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True); tid = {n: i for i, n in db.execute("select id, name from topics")}["/livox/imu"]
    rows = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid,)):
        m = deserialize_message(bytes(d), Imu); g = m.angular_velocity
        rows.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, g.x, g.y, g.z))
    return np.array(rows)


def lidar_start_end(bag, sec=1.0):
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True); tid = {n: i for i, n in db.execute("select id, name from topics")}["/livox/lidar"]
    sc = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid,)):
        m = R.conv.decode_custom_msg_numpy(bytes(d)); a = m["array"][::4]; sc.append((m["sec"] + m["nanosec"] * 1e-9, np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64)))
    t0, t1 = sc[0][0], sc[-1][0]
    def cl(lo, hi):
        X = np.vstack([p for s, p in sc if lo <= s - t0 <= hi]); r = np.linalg.norm(X, axis=1); return P.voxel(X[(r > 0.5) & (r < 40)])
    A, B = cl(0, sec), cl(t1 - t0 - sec, t1 - t0); tree = cKDTree(A); nrm, flat = P.normals(A, tree); ok = flat <= P.FLAT_MAX
    best = None
    for yaw in (0, 5, -5):
        T, inl, rms, rp = P.icp_plane(B, tree, A, nrm, P.Tz(0, 0, yaw), ok=ok)
        if best is None or inl > best[1]: best = (T, inl)
    return best[0], best[1], t1 - t0


print("== LiDAR-only first 1 s vs last 1 s (sensor frame; platform stationary)")
for name, bag in STAT.items():
    T, inl, dur = lidar_start_end(bag)
    pitch = math.degrees(-math.asin(np.clip(T[2, 0], -1, 1))); roll = math.degrees(math.atan2(T[2, 1], T[2, 2]))
    print("  %-22s %.1f s: dx %+.4f dy %+.4f dz %+.4f m (horizontal %.4f, 3D %.4f), yaw %+.3f roll %+.3f pitch %+.3f deg, inliers %.3f" % (name, dur, T[0, 3], T[1, 3], T[2, 3], math.hypot(T[0, 3], T[1, 3]), np.linalg.norm(T[:3, 3]), P.yaw_of(T), roll, pitch, inl), flush=True)
print("== gyro bias (rad/s), mean of the still part; the still part = whole bag for stationary bags, first 3 s for moving bags")
print("  %-24s %8s %8s %8s | std z | first10s z  last10s z | |bias|  bias*T yaw if uncorrected" % ("bag", "x", "y", "z"))
for name, bag in list(STAT.items()) + list(MOVE.items()):
    g = imu(bag); t = g[:, 0] - g[0, 0]; still = np.ones(len(g), bool) if name in STAT else (t < 3.0)
    b = g[still, 1:].mean(0); sd = g[still, 1:].std(0); f10 = g[t < 10, 3].mean() if name in STAT else np.nan; l10 = g[t > t[-1] - 10, 3].mean() if name in STAT else np.nan
    T = t[-1]
    print("  %-24s %+.4f %+.4f %+.4f | %.4f | %+.4f  %+.4f | %.4f  %.1f deg over %.0f s" % (name, *b, sd[2], f10, l10, np.linalg.norm(b), math.degrees(b[2] * T), T))
