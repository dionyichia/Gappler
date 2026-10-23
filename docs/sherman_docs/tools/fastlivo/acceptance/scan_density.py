#!/usr/bin/env python3
"""Offline (box): what the 2D scan from pointcloud_to_laserscan would contain, and how much of 360 degrees /cloud_registered covers.
Mimics the launch's converter: points with z in [-0.1, 0.5] m in livox_frame, range 0.1 to 40 m, nearest return per 0.00872 rad beam.
usage: scan_density.py BAG [N_SCANS]"""
import sys
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

bag = sys.argv[1]; n_scans = int(sys.argv[2]) if len(sys.argv) > 2 else 300
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=["/livox/lidar"]))
NB = int(round(2 * np.pi / 0.00872)); stats = []
while r.has_next() and len(stats) < n_scans:
    _, d, _ = r.read_next()
    m = deserialize_message(d, get_message(types["/livox/lidar"]))
    p = np.array([(q.x, q.y, q.z) for q in m.points], dtype=np.float32)
    rng = np.hypot(p[:, 0], p[:, 1]); band = (p[:, 2] >= -0.1) & (p[:, 2] <= 0.5) & (rng >= 0.1) & (rng <= 40)
    q = p[band]; ang = np.arctan2(q[:, 1], q[:, 0]); idx = ((ang + np.pi) / 0.00872).astype(int) % NB
    valid = len(np.unique(idx))
    stats.append((len(p), int(band.sum()), valid))
a = np.array(stats)
print("raw scans %d (every message from the start). beams per scan: %d" % (len(a), NB))
print("  raw points per message: median %d" % np.median(a[:, 0]))
print("  points inside the height band: median %d p5 %d p95 %d  (%.1f%% of raw)" % (np.median(a[:, 1]), np.percentile(a[:, 1], 5), np.percentile(a[:, 1], 95), 100 * np.median(a[:, 1]) / np.median(a[:, 0])))
print("  beams with a return: median %d p5 %d p95 %d of %d  -> valid-beam fraction median %.2f p5 %.2f p95 %.2f" % (
    np.median(a[:, 2]), np.percentile(a[:, 2], 5), np.percentile(a[:, 2], 95), NB, np.median(a[:, 2]) / NB, np.percentile(a[:, 2], 5) / NB, np.percentile(a[:, 2], 95) / NB))
# /cloud_registered azimuth coverage, around the sensor, using the mapper pose to bring points back to the body frame
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
r.set_filter(rosbag2_py.StorageFilter(topics=["/cloud_registered", "/aft_mapped_to_init"]))
pose = None; cov = []; counts = []
def rot(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
while r.has_next() and len(cov) < 600:
    t, d, _ = r.read_next()
    m = deserialize_message(d, get_message(types.get(t) or r.get_all_topics_and_types()[0].type)) if False else None
    if t == "/aft_mapped_to_init":
        from nav_msgs.msg import Odometry
        o = deserialize_message(d, Odometry); pose = (np.array([o.pose.pose.position.x, o.pose.pose.position.y, o.pose.pose.position.z]), rot((o.pose.pose.orientation.x, o.pose.pose.orientation.y, o.pose.pose.orientation.z, o.pose.pose.orientation.w)))
    else:
        from sensor_msgs.msg import PointCloud2
        c = deserialize_message(d, PointCloud2)
        if c.width < 50 or pose is None:
            continue
        a_ = np.frombuffer(bytes(c.data), np.uint8).reshape(c.width, c.point_step); xyz = np.ascontiguousarray(a_[:, :12]).view("<f4").reshape(-1, 3)
        body = (xyz - pose[0]) @ pose[1]  # R^T (p - t)
        ang = np.degrees(np.arctan2(body[:, 1], body[:, 0]))
        cov.append(np.ptp(ang) if np.ptp(ang) < 300 else 360.0); counts.append(len(xyz))
cov = np.array(cov)
print("/cloud_registered: %d non-empty messages sampled, points per message median %d; azimuth span around the body: median %.0f deg, p95 %.0f deg of 360" % (len(cov), np.median(counts), np.median(cov), np.percentile(cov, 95)))
