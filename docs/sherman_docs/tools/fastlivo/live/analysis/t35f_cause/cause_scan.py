"""T3.5f cause hunt: one read-only pass per bag. Compare IMU, LiDAR, pose and camera streams.
usage: cause_scan.py LABEL=BAG_DIR [...]   (needs ROS Humble + nav overlay sourced; T35_CONVERTER = path of livox_custom_to_cloud.py)"""
import importlib.util, math, os, sys
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu

spec = importlib.util.spec_from_file_location("c", os.environ.get("T35_CONVERTER", os.path.expanduser("~/rcp-Gappler/nav/robot_slam/scripts/livox_custom_to_cloud.py")))
conv = importlib.util.module_from_spec(spec); spec.loader.exec_module(conv)

def rate(ts):
    ts = np.asarray(ts); d = np.diff(ts)
    return len(ts) / (ts[-1] - ts[0]) if len(ts) > 1 else 0, d.max() if len(d) else 0, np.percentile(d, 99) if len(d) else 0

for arg in sys.argv[1:]:
    label, bag = arg.split("=", 1)
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
    rec = {}; imu = []; lid = []; pose = []; cam = []
    while r.has_next():
        t, d, ns = r.read_next()
        rec.setdefault(t, []).append(ns * 1e-9)
        if t == "/livox/imu":
            m = deserialize_message(d, Imu)
            imu.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, ns * 1e-9, m.linear_acceleration.x, m.linear_acceleration.y, m.linear_acceleration.z, m.angular_velocity.x, m.angular_velocity.y, m.angular_velocity.z))
        elif t == "/livox/lidar":
            m = conv.decode_custom_msg_numpy(bytes(d)); a = m["array"]
            lid.append((m["sec"] + m["nanosec"] * 1e-9, ns * 1e-9, len(a), int(a["t"].max()) if len(a) else 0, int((a["tag"] != 0).sum()), float(np.hypot(a["x"], a["y"]).mean()) if len(a) else 0))
        elif t == "/aft_mapped_to_init":
            m = deserialize_message(d, Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
            pose.append((ns * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
        elif t.endswith("image_raw"):
            cam.append(ns * 1e-9)
    print("=" * 20, label)
    print("topics:", {k: len(v) for k, v in sorted(rec.items())})
    imu = np.array(imu); lid = np.array(lid); pose = np.array(pose)
    if len(imu):
        hz, mx, p99 = rate(imu[:, 0])
        n0 = np.searchsorted(imu[:, 1], imu[0, 1] + 10)
        a = imu[:n0, 2:5]; g = imu[:n0, 5:8]
        am = np.linalg.norm(a, axis=1)
        print("IMU %d msgs: %.1f Hz (stamp), max gap %.3f s, p99 gap %.4f s; first 10 s: |acc| mean %.4f (units: %s), acc mean xyz %s, gyro mean xyz %s, gyro std %s" % (
            len(imu), hz, mx, p99, am.mean(), "g" if 0.5 < am.mean() < 1.5 else "m/s2", np.round(a.mean(0), 4), np.round(g.mean(0), 5), np.round(g.std(0), 5)))
        lag = imu[:, 1] - imu[:, 0]
        print("   IMU receipt-minus-stamp lag: mean %.4f s, max %.4f s, stamp-recv offset drift %.4f s" % (lag.mean(), lag.max(), lag[-1] - lag[0]))
    if len(lid):
        hz, mx, p99 = rate(lid[:, 0])
        print("LiDAR %d scans: %.2f Hz, max gap %.3f s, p99 gap %.4f s; points/scan mean %.0f min %d max %d; offset_time max mean %.1f ms (max %.1f); tag!=0 mean %.0f; mean range %.2f m" % (
            len(lid), hz, mx, p99, lid[:, 2].mean(), lid[:, 2].min(), lid[:, 2].max(), lid[:, 3].mean() * 1e-6, lid[:, 3].max() * 1e-6, lid[:, 4].mean(), lid[:, 5].mean()))
        lag = lid[:, 1] - lid[:, 0]
        print("   LiDAR receipt-minus-stamp lag: mean %.4f s, max %.4f s" % (lag.mean(), lag.max()))
    if cam:
        hz, mx, p99 = rate(cam); print("camera %d frames: %.1f Hz (receipt), max gap %.3f s, p99 %.4f s" % (len(cam), hz, mx, p99))
    if len(pose):
        t = pose[:, 0] - pose[0, 0]; xy = pose[:, 1:3]; steps = np.hypot(*np.diff(xy, axis=0).T)
        hz, mx, p99 = rate(pose[:, 0])
        print("poses %d: %.1f Hz, max gap %.3f s; path %.1f m, duration %.1f s, mean speed %.2f m/s, max 1 s speed %.2f m/s" % (len(pose), hz, mx, steps.sum(), t[-1], steps.sum() / t[-1],
              max(np.hypot(*(xy[min(i + 20, len(xy) - 1)] - xy[i])) for i in range(0, len(xy), 5))))
        print("   raw first pose %s ; raw last pose %s" % (np.round(pose[0, 1:4], 3), np.round(pose[-1, 1:4], 3)))
        print("   raw last-minus-first xyz %s (horizontal %.3f m, vertical %.3f m)" % (np.round(pose[-1, 1:4] - pose[0, 1:4], 3), math.hypot(*(pose[-1, 1:3] - pose[0, 1:3])), pose[-1, 3] - pose[0, 3]))
        z = pose[:, 3]; print("   z range %.3f m (min %.3f max %.3f)" % (z.max() - z.min(), z.min(), z.max()))
