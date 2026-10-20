import time, struct
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = "/home/rcp2026/rcp-Gappler/log/t59-fastlivo/log/t35d-attended-20261020.raLTgE/run/bag/handdriven1"
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=["/livox/lidar"]))
raws = []
while r.has_next() and len(raws) < 60:
    raws.append(r.read_next()[1])
PT = np.dtype([('t', '<u4'), ('x', '<f4'), ('y', '<f4'), ('z', '<f4'), ('refl', 'u1'), ('tag', 'u1'), ('line', 'u1'), ('pad', 'u1')])


def decode(b):
    """CDR bytes of livox_ros_driver2/CustomMsg -> (sec, nsec, frame_id, timebase, structured points)."""
    d = memoryview(b)[4:]  # drop the 4-byte encapsulation header; alignment is relative to what follows
    sec, nsec, n = struct.unpack_from('<iII', d, 0); fid = bytes(d[12:12 + n - 1]).decode()
    o = 12 + n
    o = (o + 7) & ~7
    timebase, = struct.unpack_from('<Q', d, o); o += 8
    pn, lid = struct.unpack_from('<IB', d, o); o += 4 + 1 + 3
    o = (o + 3) & ~3
    cnt, = struct.unpack_from('<I', d, o); o += 4
    buf = bytes(d[o:o + cnt * 20 - 1]) + b'\0'
    return sec, nsec, fid, timebase, pn, np.frombuffer(buf, PT, count=cnt)


t = time.time(); msgs = [deserialize_message(b, get_message(types["/livox/lidar"])) for b in raws]; t_des = (time.time() - t) / len(raws)
t = time.time(); xyz_a = [np.array([(p.x, p.y, p.z) for p in m.points]) for m in msgs]; t_list = (time.time() - t) / len(raws)
t = time.time(); dec = [decode(b) for b in raws]; t_np = (time.time() - t) / len(raws)
ok = True
for m, a, d in zip(msgs, xyz_a, dec):
    sec, nsec, fid, tb, pn, pts = d
    ok &= (m.header.stamp.sec == sec and m.header.stamp.nanosec == nsec and m.header.frame_id == fid and m.timebase == tb and m.point_num == pn == len(m.points) == len(pts))
    ok &= np.array_equal(a.astype(np.float32), np.stack([pts['x'], pts['y'], pts['z']], 1))
    ok &= np.array_equal(np.array([p.reflectivity for p in m.points]), pts['refl']) and np.array_equal(np.array([p.offset_time for p in m.points]), pts['t'])
print("messages", len(raws), "points/msg", len(msgs[0].points), "frame", dec[0][2])
print("rclpy deserialize: %.1f ms/msg | + python list to xyz: %.1f ms/msg | numpy decode: %.2f ms/msg" % (t_des * 1e3, t_list * 1e3, t_np * 1e3))
print("numpy decode equals rclpy on every field of every message:", bool(ok))
