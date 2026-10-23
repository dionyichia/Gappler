#!/usr/bin/env python3
"""How many scans SLAM Toolbox would process (box, offline). Its rule: process a scan only if the robot moved at least
minimum_travel_distance or turned at least minimum_travel_heading since the last processed scan (the first scan always is).
Poses are the bridge's odom -> robot_base_link, one final pose per scan (50 ms burst rule), from the bag.
usage: scans_processed.py BAG BRIDGE_MODULE_PATH"""
import importlib.util, math, sys
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry

bag, mod = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("b", mod); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
r.set_filter(rosbag2_py.StorageFilter(topics=["/aft_mapped_to_init"]))
core = b.OdomFromMapper((0.191, 0.02329, 0.15588))
rows = []  # (record time s, x, y, yaw)
while r.has_next():
    _, d, rec = r.read_next()
    o = deserialize_message(d, Odometry); p, q = o.pose.pose.position, o.pose.pose.orientation
    pos, quat = core.update((p.x, p.y, p.z), (q.x, q.y, q.z, q.w))
    m = b.quat_to_mat(quat); rows.append((rec * 1e-9, pos[0], pos[1], math.atan2(m[1][0], m[0][0])))
a = np.array(rows); t = a[:, 0]
last_of_burst = np.r_[np.diff(t) > 0.05, True]       # the final pose of each scan
s = a[last_of_burst]; s[:, 0] -= s[0, 0]
print("%s: %d scans (final poses)" % (bag.split("/")[-2] if bag.endswith("/bag") else bag.split("/")[-1], len(s)))
for dist, head in ((0.1, 0.1), (0.0, 0.0)):
    done = [0]; last = s[0]
    for i in range(1, len(s)):
        dyaw = abs((s[i, 3] - last[3] + math.pi) % (2 * math.pi) - math.pi)
        if math.hypot(s[i, 1] - last[1], s[i, 2] - last[2]) >= dist and True or dyaw >= head:
            pass
        if (math.hypot(s[i, 1] - last[1], s[i, 2] - last[2]) >= dist) or (dyaw >= head):
            done.append(i); last = s[i]
    done = np.array(done)
    cnt = lambda T: int((s[done, 0] <= T).sum())
    print("  min travel %.1f m / %.1f rad: processed in first 3 s %d, 6 s %d, 15 s %d, all %d of %d" % (dist, head, cnt(3), cnt(6), cnt(15), len(done), len(s)))
print("  robot moved in the first 3 s: %.3f m, turned %.2f deg; first 6 s: %.3f m, %.2f deg" % tuple(
    v for T in (3, 6) for v in (math.hypot(*(s[s[:, 0] <= T][-1, 1:3] - s[0, 1:3])), math.degrees(abs(s[s[:, 0] <= T][-1, 3] - s[0, 3])))))
