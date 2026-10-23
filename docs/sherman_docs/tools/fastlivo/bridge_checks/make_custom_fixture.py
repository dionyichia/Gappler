"""Box only (needs rosbag2_py and the nav overlay): cut a real CustomMsg to N points and write bench/golden/livox_custom_msg.json
(CDR bytes as hex, plus the values rclpy decodes from them), so the L0 test can check the stdlib decoder with no ROS.
usage: make_custom_fixture.py BAG OUT_JSON [N]"""
import json, sys
import rosbag2_py
from livox_ros_driver2.msg import CustomMsg
from rclpy.serialization import deserialize_message, serialize_message

bag, out = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='sqlite3'), rosbag2_py.ConverterOptions('', ''))
r.set_filter(rosbag2_py.StorageFilter(topics=['/livox/lidar']))
fixtures = []
for take in (n, 1, 0):  # a normal cut, a single point (no padding case), and an empty message
    r.seek(0) if hasattr(r, 'seek') else None
    r2 = rosbag2_py.SequentialReader()
    r2.open(rosbag2_py.StorageOptions(uri=bag, storage_id='sqlite3'), rosbag2_py.ConverterOptions('', ''))
    r2.set_filter(rosbag2_py.StorageFilter(topics=['/livox/lidar']))
    _, data, _ = r2.read_next()
    m = deserialize_message(data, CustomMsg)
    m.points = list(m.points)[:take]
    m.point_num = take
    raw = bytes(serialize_message(m))
    back = deserialize_message(raw, CustomMsg)
    fixtures.append({
        'points_wanted': take, 'cdr_hex': raw.hex(),
        'sec': back.header.stamp.sec, 'nanosec': back.header.stamp.nanosec, 'frame_id': back.header.frame_id,
        'timebase': back.timebase, 'point_num': back.point_num, 'lidar_id': back.lidar_id,
        'points': [[p.offset_time, p.x, p.y, p.z, p.reflectivity, p.tag, p.line] for p in back.points]})
json.dump({'note': 'real handdriven1 CustomMsg cut to N points; values are what rclpy decodes from cdr_hex', 'fixtures': fixtures}, open(out, 'w'), indent=1)
print('wrote', out, [f['points_wanted'] for f in fixtures], 'bytes', [len(f['cdr_hex']) // 2 for f in fixtures])
