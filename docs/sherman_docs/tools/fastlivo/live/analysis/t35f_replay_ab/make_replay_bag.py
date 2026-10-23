"""T3.5f replay A/B: write a 4-topic replay input bag from a live recording, optionally with the glass/mirror region removed from /livox/lidar.
usage: make_replay_bag.py SRC_BAG DST_BAG [--keep-box X0 X1 Y0 Y1]      |      make_replay_bag.py --selftest
Why a copy: ros2 bag play plays every recorded topic, and the live bags also hold the mapper's own outputs (/aft_mapped_to_init, /cloud_registered,
/tf ...), which would collide with the replayed mapper's. The copy holds exactly the four input topics, original timestamps, original message bytes.
--keep-box: a LiDAR point survives only if its odom-frame (x, y) lies inside the box. World position = bag pose (nearest /aft_mapped_to_init stamp, one
pose per scan, no deskew) applied to the point plus the staged LiDAR->IMU translation. The bag pose carries the live drift (about 0.3 m by the end), which
is why the box has a margin. Everything else in a filtered message (header, timebase, per-point offset_time/line/tag) is untouched; point_num is updated.
Needs ROS Humble + nav overlay sourced; T35_CONVERTER = path of livox_custom_to_cloud.py."""
import glob, importlib.util, os, sqlite3, sys
import numpy as np

INPUTS = ("/livox/lidar", "/livox/imu", "/camera/camera/color/image_raw", "/camera/camera/color/camera_info")
T_IL = np.array([-0.011, -0.02329, 0.04412])  # extrin_calib.extrinsic_T of the replay mapper YAML, R = identity


def quat_to_R(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def keep_mask(xyz, pose, box):
    """xyz (N,3) sensor-frame points, pose (x y z qx qy qz qw), box (x0, x1, y0, y1) -> bool (N,)"""
    w = (quat_to_R(*pose[3:7]) @ (xyz.astype(float) + T_IL).T).T + np.asarray(pose[:3])
    return (w[:, 0] >= box[0]) & (w[:, 0] <= box[1]) & (w[:, 1] >= box[2]) & (w[:, 1] <= box[3])


def selftest():
    pts = np.array([[1.0, 0.0, 0.0], [5.0, 0.0, 0.0]])
    ident = (0, 0, 0, 0, 0, 0, 1)
    assert keep_mask(pts, ident, (-2, 2, -2, 2)).tolist() == [True, False]
    yaw90 = (0, 0, 0, 0, 0, 0.70710678, 0.70710678)   # +x sensor axis points along world +y
    assert keep_mask(pts, yaw90, (-2, 2, -2, 2)).tolist() == [True, False]
    assert keep_mask(pts, (3, 0, 0, 0, 0, 0, 1), (-2, 2, -2, 2)).tolist() == [False, False]  # moved 3 m along x
    print("selftest ok")


def main(src, dst, box):
    import rosbag2_py
    from rclpy.serialization import deserialize_message, serialize_message
    from nav_msgs.msg import Odometry
    from livox_ros_driver2.msg import CustomMsg
    spec = importlib.util.spec_from_file_location("c", os.environ["T35_CONVERTER"])
    conv = importlib.util.module_from_spec(spec); spec.loader.exec_module(conv)
    poses = None
    if box:
        db = sqlite3.connect("file:%s?mode=ro" % glob.glob(src + "/*.db3")[0], uri=True)
        tid = db.execute("select id from topics where name='/aft_mapped_to_init'").fetchone()[0]
        rows = []
        for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid,)):
            m = deserialize_message(bytes(d), Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
            rows.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
        poses = np.array(rows)
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=src, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
    w = rosbag2_py.SequentialWriter()
    w.open(rosbag2_py.StorageOptions(uri=dst, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
    for t in r.get_all_topics_and_types():
        if t.name in INPUTS:
            w.create_topic(t)
    n = {k: 0 for k in INPUTS}; before = after = 0
    while r.has_next():
        topic, data, ts = r.read_next()
        if topic not in INPUTS:
            continue
        if box and topic == "/livox/lidar":
            raw = bytes(data); dec = conv.decode_custom_msg_numpy(raw); a = dec["array"]
            i = min(max(int(np.searchsorted(poses[:, 0], dec["sec"] + dec["nanosec"] * 1e-9)), 0), len(poses) - 1)
            keep = keep_mask(np.stack([a["x"], a["y"], a["z"]], 1), poses[i, 1:8], box)
            m = deserialize_message(raw, CustomMsg)
            m.points = [p for p, k in zip(m.points, keep) if k]; m.point_num = len(m.points)
            data = serialize_message(m); before += len(keep); after += int(keep.sum())
        w.write(topic, bytes(data), ts); n[topic] += 1
    print("wrote", dst, n)
    if box:
        print("lidar points kept %d of %d (%.1f %% removed), box %s" % (after, before, 100 * (1 - after / before), box))


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        main(sys.argv[1], sys.argv[2], tuple(map(float, sys.argv[4:8])) if "--keep-box" in sys.argv else None)
