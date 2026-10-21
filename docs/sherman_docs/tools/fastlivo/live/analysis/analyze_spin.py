import math, sys
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
T = {'corrected_constant': np.array([0.191, 0.023, 0.156]), 'precorrection_constant': np.array([0.169, -0.023, 0.244])}
def load(bag):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='sqlite3'), rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=['/aft_mapped_to_init']))
    rows = []
    while r.has_next():
        topic, data, t = r.read_next()
        m = deserialize_message(data, get_message(types[topic]))
        p, q = m.pose.pose.position, m.pose.pose.orientation
        rows.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
    return np.array(rows)
def rot(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
a = load(sys.argv[1]); t = a[:, 0] - a[0, 0]
yaw = np.unwrap([math.atan2(2*(r[7]*r[6]+r[4]*r[5]), 1-2*(r[5]**2+r[6]**2)) for r in a])
dyaw = np.degrees(yaw - yaw[0])
print('msgs', len(a), 'duration %.1f s' % t[-1], 'total yaw change %.1f deg, min %.1f max %.1f' % (dyaw[-1], dyaw.min(), dyaw.max()))
# turning segment: from first to last time yaw is more than 3 deg from the start/end plateaus
moving = np.where(np.abs(np.gradient(np.degrees(yaw), t)) > 5)[0]
if len(moving) < 5: print('NO ROTATION DETECTED'); sys.exit()
i0, i1 = max(moving[0] - 5, 0), min(moving[-1] + 5, len(a) - 1)
print('turn segment %.1f s to %.1f s (%.1f s long), yaw swept %.1f deg' % (t[i0], t[i1], t[i1]-t[i0], dyaw[i1]-dyaw[i0]))
seg = slice(i0, i1 + 1)
paft = a[seg, 1:4]
for name, c in T.items():
    base = np.array([a[i, 1:4] - rot(a[i, 4:8]) @ c for i in range(i0, i1 + 1)])
    xy = base[:, :2]; ctr = xy.mean(0); rad = np.linalg.norm(xy - ctr, axis=1)
    print('reconstructed base with %-22s: xy spread max radius %.3f m, std %.3f m, peak-to-peak x %.3f y %.3f, z p2p %.3f' % (name, rad.max(), rad.std(), np.ptp(xy[:, 0]), np.ptp(xy[:, 1]), np.ptp(base[:, 2])))
xy = paft[:, :2]; ctr = xy.mean(0); rad = np.linalg.norm(xy - ctr, axis=1)
print('raw mapper pose (IMU) circle: radius mean %.3f m, max %.3f, min %.3f' % (rad.mean(), rad.max(), rad.min()))
for lab, sl in (('before turn (still)', slice(0, max(i0 - 5, 2))), ('after turn (still)', slice(min(i1 + 5, len(a) - 2), len(a)))):
    p = a[sl, 1:4]; print('%s: n=%d, position std %.4f m' % (lab, len(p), p.std(0).max() if len(p) > 1 else float('nan')))
print('--- fit: p_xy(t) = smooth drift (poly of given order) + Rz(yaw)(t)·t_xy ; t_xy = effective IMU position in the base frame')
tt = (t[i0:i1+1] - t[i0]) / (t[i1] - t[i0]); P = a[i0:i1+1, 1:3]; yw = yaw[i0:i1+1]
for order in (1, 2, 3, 4):
    cols = []
    for ax in (0, 1):
        for k in range(order + 1):
            c = np.zeros(len(tt) * 2); c[ax::2] = tt ** k; cols.append(c)
    cx = np.zeros(len(tt) * 2); cx[0::2] = np.cos(yw); cx[1::2] = np.sin(yw)
    cy = np.zeros(len(tt) * 2); cy[0::2] = -np.sin(yw); cy[1::2] = np.cos(yw)
    A = np.column_stack(cols + [cx, cy]); y = P.reshape(-1)
    sol, res, *_ = np.linalg.lstsq(A, y, rcond=None); rms = math.sqrt(np.mean((A @ sol - y) ** 2))
    print('order %d: t_xy = (%.3f, %.3f) m, |t_xy| %.3f, fit rms %.4f m' % (order, sol[-2], sol[-1], math.hypot(sol[-2], sol[-1]), rms))
print('candidates: corrected (0.191, 0.023) |0.192|; pre-correction (0.169, -0.023) |0.171|')
