import sys, json, struct, math
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
bag = sys.argv[1]
reader = rosbag2_py.SequentialReader()
reader.open(rosbag2_py.StorageOptions(uri=bag, storage_id='sqlite3'), rosbag2_py.ConverterOptions('', ''))
types = {t.name: t.type for t in reader.get_all_topics_and_types()}
reader.set_filter(rosbag2_py.StorageFilter(topics=['/aft_mapped_to_init', '/cloud_registered']))
traj, pts, k = [], [], 0
rng = np.random.default_rng(0)
t0 = None
while reader.has_next():
    topic, data, t = reader.read_next()
    msg = deserialize_message(data, get_message(types[topic]))
    s = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
    if t0 is None: t0 = s
    if topic == '/aft_mapped_to_init':
        p = msg.pose.pose.position; traj.append([round(s - t0, 3), round(p.x, 4), round(p.y, 4), round(p.z, 4)])
    elif msg.width > 0 and len(msg.data) > 0:
        k += 1
        if k % 6: continue
        n = msg.width; a = np.frombuffer(msg.data, dtype=np.uint8).reshape(n, msg.point_step)
        xyz = a[:, 0:12].copy().view(np.float32).reshape(n, 3)
        rgb = a[:, 16:20]
        idx = rng.choice(n, size=min(n, 180), replace=False)
        for i in idx:
            pts.append([round(float(xyz[i,0]),3), round(float(xyz[i,1]),3), round(float(xyz[i,2]),3), int(rgb[i,2]), int(rgb[i,1]), int(rgb[i,0])])
json.dump({'traj': traj, 'pts': pts}, open(sys.argv[2], 'w'))
print('traj', len(traj), 'pts', len(pts))
