import math, sys, collections
sys.path.insert(0, sys.argv[2])
import replay
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
bag = sys.argv[1]
reader = rosbag2_py.SequentialReader()
reader.open(rosbag2_py.StorageOptions(uri=bag, storage_id='sqlite3'), rosbag2_py.ConverterOptions('', ''))
types = {t.name: t.type for t in reader.get_all_topics_and_types()}
reader.set_filter(rosbag2_py.StorageFilter(topics=['/aft_mapped_to_init', '/cloud_registered']))
odom, clouds = [], collections.Counter()
col_pts, bad_pose, stamps_c = [], 0, []
while reader.has_next():
    topic, data, t = reader.read_next()
    msg = deserialize_message(data, get_message(types[topic]))
    s = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
    if topic == '/aft_mapped_to_init':
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        if not replay.valid_pose([p.x, p.y, p.z], [q.x, q.y, q.z, q.w]): bad_pose += 1
        yaw = math.atan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z))
        odom.append((s, p.x, p.y, p.z, yaw, msg.header.frame_id, msg.child_frame_id))
    else:
        ok, reason, bad, total = replay.valid_cloud(msg)
        if ok: clouds['ok_coloured'] += 1; col_pts.append(total)
        elif reason == 'empty_or_nonpositive_dimensions' and len(msg.data) == 0 and len(msg.fields) == 0: clouds['heartbeat_default_empty'] += 1
        elif reason == 'empty_or_nonpositive_dimensions' and len(msg.data) == 0: clouds['fielded_zero_point'] += 1
        else: clouds['INVALID_' + reason] += 1
        stamps_c.append(s)
print('odom msgs', len(odom), 'invalid poses', bad_pose, 'frames', {(o[5], o[6]) for o in odom})
print('clouds', dict(clouds), 'coloured points median', sorted(col_pts)[len(col_pts)//2], 'min', min(col_pts), 'max', max(col_pts))
back = sum(1 for a, b in zip(odom, odom[1:]) if b[0] < a[0]); print('odom backward stamps', back, 'cloud backward stamps', sum(1 for a, b in zip(stamps_c, stamps_c[1:]) if b < a))
gaps = [(b[0]-a[0]) for a, b in zip(odom, odom[1:])]; print('odom gap max %.3f s, >0.2 s: %d' % (max(gaps), sum(g > 0.2 for g in gaps)))
d = [math.dist(a[1:4], b[1:4]) for a, b in zip(odom, odom[1:])]
speed = [x / g for x, g in zip(d, gaps) if g > 0.01]
print('path length %.2f m, max step %.3f m, max speed %.2f m/s, median speed %.2f' % (sum(d), max(d), max(speed), sorted(speed)[len(speed)//2]))
a, b = odom[0], odom[-1]
print('start xyz %.3f %.3f %.3f yaw %.1f deg' % (a[1], a[2], a[3], math.degrees(a[4])))
print('end   xyz %.3f %.3f %.3f yaw %.1f deg' % (b[1], b[2], b[3], math.degrees(b[4])))
print('return error: horizontal %.3f m, vertical %.3f m, yaw %.1f deg' % (math.hypot(b[1]-a[1], b[2]-a[2]), b[3]-a[3], math.degrees(math.atan2(math.sin(b[4]-a[4]), math.cos(b[4]-a[4])))))
print('max distance from start %.2f m, z range %.3f m' % (max(math.dist(o[1:4], a[1:4]) for o in odom), max(o[3] for o in odom)-min(o[3] for o in odom)))
