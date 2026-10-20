import struct
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
BAG = "/home/rcp2026/rcp-Gappler/log/t59-fastlivo/log/t35d-attended-20261020.raLTgE/run/bag/handdriven1"
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=["/livox/lidar", "/aft_mapped_to_init", "/camera/camera/color/image_raw"]))
L, O, I = [], [], []
while r.has_next():
    topic, data, rec = r.read_next()
    sec, nsec = struct.unpack_from("<iI", data, 4)  # all three headers start with stamp
    if topic == "/livox/lidar": L.append((sec + nsec * 1e-9, rec * 1e-9))
    elif topic == "/aft_mapped_to_init": O.append((sec + nsec * 1e-9, rec * 1e-9))
    else: I.append((sec + nsec * 1e-9, rec * 1e-9))
L, O, I = map(np.array, (L, O, I))
# source scan = latest scan that had ARRIVED (bag record time) before the odometry was stamped
idx = np.searchsorted(L[:, 1], O[:, 0], side="right") - 1
ok = idx >= 0
proc = O[ok, 0] - L[idx[ok], 1]          # odom stamp minus the arrival of its source scan
vs_start = O[ok, 0] - L[idx[ok], 0]      # odom stamp minus the scan's own header stamp (scan start)
vs_end = O[ok, 0] - (L[idx[ok], 0] + 0.1)  # minus scan end by period
for name, a in (("odom stamp - source scan header stamp (start)", vs_start), ("odom stamp - source scan end (start+0.1 s)", vs_end), ("odom stamp - source scan arrival (bag record)", proc)):
    print("%-48s p50 %6.1f ms  p95 %6.1f ms  p99 %6.1f ms  max %6.1f ms" % (name, *(np.percentile(a, [50, 95, 99]) * 1e3), a.max() * 1e3))
first = np.r_[True, idx[ok][1:] != idx[ok][:-1]]
for nm, sel in (("first odom after each scan", first), ("second odom after each scan", ~first)):
    print("  %-30s n=%4d: stamp - scan end p50 %.1f ms p95 %.1f ms" % (nm, sel.sum(), *(np.percentile(vs_end[sel], [50, 95]) * 1e3)))
# the second odom is likely the VIO update: compare with the nearest image header stamp before it
j = np.searchsorted(I[:, 1], O[:, 0], side="right") - 1
good = j >= 0
print("odom stamp minus latest ARRIVED image's header stamp: p50 %.1f ms p95 %.1f ms (image arrival lag: record-stamp p50 %.1f ms)" % (*(np.percentile(O[good, 0] - I[j[good], 0], [50, 95]) * 1e3), np.median(I[:, 1] - I[:, 0]) * 1e3))
