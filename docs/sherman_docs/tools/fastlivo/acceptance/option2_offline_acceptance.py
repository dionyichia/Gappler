#!/usr/bin/env python3
"""T3.5e option 2, Phase 3: offline acceptance from the T3.5d bags. Box only. No hardware, no mapper, no Docker, no robot command.

  map      handdriven1 through bridge + converter + pointcloud_to_laserscan + SLAM Toolbox (mapping). Saves the 2D map, the
           serialized pose graph, a PCD built from the bag's /cloud_registered (voxel 0.05 m, mapper frame camera_init) and a
           sidecar JSON with map -> odom at save time and camera_init -> odom (the PCD's frame relative to odom).
  localize spin-corrected through the same chain with SLAM Toolbox in localization mode on that pose graph and an initial guess
           (x, y, yaw). Samples map -> odom, which is the pose of the spin start in the map (odom equals the base at startup).
  scanonly same as map but with the odom edge held at identity (SLAM Toolbox on scan matching alone), a baseline for what the
           FAST-LIVO2 odometry adds. No wheel-odom map of this lab exists to compare with.

Run on the domain given by ROS_DOMAIN_ID (use an isolated one) with ROS_LOCALHOST_ONLY=1.
Playback is only /aft_mapped_to_init and /livox/lidar: the bags' recorded /tf, /tf_static and mapper outputs are never played (the
PCD is read from the bag file). --stamp scanend re-stamps each odometry burst to its source scan's end time, emulating a fork patch
of LIVMapper.cpp:1561 (stamp = LidarMeasures.last_lio_update_time); --stamp recorded keeps the stamps as recorded.
usage: option2_offline_acceptance.py map|scanonly|localize OUT_DIR [--stamp recorded|scanend] [--guess X Y YAW_DEG] [--bag PATH] [--rate R]
"""
import argparse, importlib.util, json, math, os, signal, subprocess, sys, tempfile, time
from pathlib import Path

REPO = Path(os.environ.get("GAPPLER_REPO", Path.home() / "rcp-Gappler"))
SRC = Path(os.environ.get("OPTION2_SRC", REPO))  # where nav/robot_slam lives (the mirror of this branch)
A = REPO / "log/t59-fastlivo/log/t35d-attended-20261020.raLTgE"
BAGS = {"map": A / "run/bag/handdriven1", "scanonly": A / "run/bag/handdriven1", "localize": A / "spin-corrected/bag"}
SCAN_PARAMS = dict(target_frame="livox_frame", transform_tolerance=0.01, min_height=-0.1, max_height=0.5, angle_min=-3.14159,
                   angle_max=3.14159, angle_increment=0.00872, scan_time=0.1, range_min=0.1, range_max=40.0, use_inf=True)


def start(cmd, log, env=None):
    return subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT, start_new_session=True, env=env)


def stop(p):
    if p is None or p.poll() is not None:
        return
    for sig, wait in ((signal.SIGINT, 6), (signal.SIGTERM, 4), (signal.SIGKILL, 2)):
        try:
            os.killpg(p.pid, sig); p.wait(wait); return
        except (subprocess.TimeoutExpired, ProcessLookupError):
            continue


RESTAMP_RELAY = """
import struct
import rclpy
from livox_ros_driver2.msg import CustomMsg
from nav_msgs.msg import Odometry
from rclpy.node import Node
rclpy.init(); n = Node('restamp_odom'); pub = n.create_publisher(Odometry, '/aft_mapped_restamped', 10)
st = {'scan_end': None, 'last_arrival': None, 'burst_end': None}
def on_scan(raw):  # header stamp is the scan start, the scan lasts 0.1 s
    sec, nsec = struct.unpack_from('<iI', raw, 4); st['scan_end'] = sec + nsec * 1e-9 + 0.1
def on_odom(m):
    now = n.get_clock().now().nanoseconds * 1e-9
    if st['scan_end'] is None:
        return
    if st['last_arrival'] is None or now - st['last_arrival'] > 0.05:  # a new burst: the poses of one scan arrive within 50 ms
        st['burst_end'] = st['scan_end']
    st['last_arrival'] = now
    t = st['burst_end']; m.header.stamp.sec = int(t); m.header.stamp.nanosec = int(round((t - int(t)) * 1e9)) % 1000000000
    pub.publish(m)
n.create_subscription(CustomMsg, '/livox/lidar', on_scan, 10, raw=True)
n.create_subscription(Odometry, '/aft_mapped_to_init', on_odom, 10)
rclpy.spin(n)
"""


def pcd_from_bag(bag):
    """Accumulate the mapper's /cloud_registered straight from the bag file (nothing is played). Returns an (N, 3) float32 array."""
    import numpy as np
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    if "/cloud_registered" not in types:
        return np.empty((0, 3), "<f4")
    r.set_filter(rosbag2_py.StorageFilter(topics=["/cloud_registered"]))
    chunks = []
    while r.has_next():
        _, data, _ = r.read_next()
        m = deserialize_message(data, get_message(types["/cloud_registered"]))
        if m.width:
            a = np.frombuffer(bytes(m.data), np.uint8).reshape(m.width, m.point_step)
            chunks.append(np.ascontiguousarray(a[:, :12]).view("<f4").reshape(-1, 3).copy())
    return np.vstack(chunks) if chunks else np.empty((0, 3), "<f4")


def load_bridge():
    spec = importlib.util.spec_from_file_location("fastlivo_odom_bridge", SRC / "nav/robot_slam/scripts/fastlivo_odom_bridge.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("map", "scanonly", "localize")); ap.add_argument("out")
    ap.add_argument("--stamp", choices=("recorded", "scanend"), default="recorded")
    ap.add_argument("--slam-param", action="append", default=[], metavar="KEY=VALUE", help="extra SLAM Toolbox parameter override, repeatable")
    ap.add_argument("--guess", nargs=3, type=float, default=[2.0, 1.2, 0.0]); ap.add_argument("--bag"); ap.add_argument("--rate", type=float, default=1.0)
    ap.add_argument("--graph", help="pose graph prefix for localize (default OUT/../map/session)")
    args = ap.parse_args()
    import numpy as np
    import rclpy
    from geometry_msgs.msg import TransformStamped
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import PointCloud2
    from tf2_ros import Buffer, TransformListener, StaticTransformBroadcaster, TransformBroadcaster
    bridge = load_bridge()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    bag = Path(args.bag) if args.bag else BAGS[args.mode]
    folder = out / "logs"; folder.mkdir(exist_ok=True)
    qos_file = folder / "qos.yaml"
    qos_file.write_text("".join("%s:\n  history: keep_last\n  depth: 10\n  reliability: reliable\n  durability: volatile\n" % t
                                for t in ("/livox/lidar", "/aft_mapped_to_init")))
    procs = []
    sl = lambda *a: [str(x) for x in a]
    rclpy.init()
    node = Node("option2_acceptance")
    buf = Buffer(); TransformListener(buf, node)
    first_pose = []; scan_stats = []
    from sensor_msgs.msg import LaserScan
    def on_scan(m):
        r_ = np.array(m.ranges, dtype=np.float64); scan_stats.append((len(r_), int(np.isfinite(r_).sum())))
    node.create_subscription(LaserScan, "/scan", on_scan, 10)
    node.create_subscription(Odometry, "/aft_mapped_to_init", lambda m: first_pose.append(m) if not first_pose else None, 10)

    def spin(sec):
        end = time.monotonic() + sec
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.02)

    try:
        procs.append(start(["ros2", "run", "tf2_ros", "static_transform_publisher", "--x", "0.18", "--y", "0", "--z", "0.2", "--yaw", "0", "--pitch", "0",
                            "--roll", "0", "--frame-id", "robot_base_link", "--child-frame-id", "livox_frame"], folder / "static_tf.log"))
        if args.mode == "scanonly":  # odom held at identity: scan matching alone
            procs.append(start([sys.executable, "-c", "import rclpy\nfrom geometry_msgs.msg import TransformStamped\nfrom rclpy.node import Node\nfrom tf2_ros import TransformBroadcaster\n"
                                "rclpy.init(); n=Node('identity_odom'); b=TransformBroadcaster(n)\n"
                                "def t():\n  m=TransformStamped(); m.header.stamp=n.get_clock().now().to_msg(); m.header.frame_id='odom'; m.child_frame_id='robot_base_link'; m.transform.rotation.w=1.0; b.sendTransform(m)\n"
                                "n.create_timer(0.02,t); rclpy.spin(n)"], folder / "identity_odom.log"))
            # bag time stamps are old: publish identity with the bag's stamps instead, via a small relay below
            stop(procs.pop())
            relay = ("import rclpy\nfrom geometry_msgs.msg import TransformStamped\nfrom nav_msgs.msg import Odometry\nfrom rclpy.node import Node\nfrom tf2_ros import TransformBroadcaster\n"
                     "rclpy.init(); n=Node('identity_odom'); b=TransformBroadcaster(n)\n"
                     "def cb(o):\n  m=TransformStamped(); m.header=o.header; m.header.frame_id='odom'; m.child_frame_id='robot_base_link'; m.transform.rotation.w=1.0; b.sendTransform(m)\n"
                     "n.create_subscription(Odometry,'/aft_mapped_to_init',cb,10); rclpy.spin(n)")
            procs.append(start([sys.executable, "-c", relay], folder / "identity_odom.log"))
        else:
            bridge_args = ["--params-file", str(SRC / "nav/robot_slam/config/fastlivo_bridge.yaml")]
            if args.stamp == "scanend":
                procs.append(start([sys.executable, "-c", RESTAMP_RELAY], folder / "restamp.log"))
                bridge_args += ["-p", "mapper_topic:=/aft_mapped_restamped"]
            procs.append(start([sys.executable, str(SRC / "nav/robot_slam/scripts/fastlivo_odom_bridge.py"), "--ros-args"] + bridge_args, folder / "bridge.log"))
        procs.append(start([sys.executable, str(SRC / "nav/robot_slam/scripts/livox_custom_to_cloud.py")], folder / "converter.log"))
        scan_args = []
        for k, v in SCAN_PARAMS.items():
            scan_args += ["-p", "%s:=%s" % (k, str(v).lower() if isinstance(v, bool) else v)]
        procs.append(start(["ros2", "run", "pointcloud_to_laserscan", "pointcloud_to_laserscan_node", "--ros-args"] + scan_args + ["-r", "cloud_in:=/cloud_relay"], folder / "scan.log"))
        if args.mode == "localize":
            graph = args.graph or str(out.parent / "map/session")
            params = ["--params-file", str(SRC / "nav/robot_slam/config/slam_toolbox_localization.yaml"), "-p", "map_file_name:=" + graph,
                      "-p", "map_start_pose:=[%s, %s, %s]" % (args.guess[0], args.guess[1], math.radians(args.guess[2]))]
            exe = "localization_slam_toolbox_node"
        else:
            params = ["--params-file", str(SRC / "nav/robot_slam/config/slam_toolbox.yaml")]
            exe = "async_slam_toolbox_node"
        for kv in args.slam_param:
            params += ["-p", kv.replace("=", ":=", 1)]
        procs.append(start(["ros2", "run", "slam_toolbox", exe, "--ros-args"] + params + ["-r", "scan:=/scan"], folder / "slam_toolbox.log"))
        spin(6.0)
        player = start(["ros2", "bag", "play", str(bag), "--rate", str(args.rate), "--topics", "/aft_mapped_to_init", "/livox/lidar",
                        "--qos-profile-overrides-path", str(qos_file)], folder / "player.log")
        procs.append(player)
        samples = []; t0 = time.monotonic()
        while player.poll() is None and time.monotonic() - t0 < 400:
            spin(0.5)
            try:
                t = buf.lookup_transform("map", "odom", rclpy.time.Time())
                q = t.transform.rotation
                yaw = math.degrees(math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z)))
                samples.append((round(time.monotonic() - t0, 1), t.transform.translation.x, t.transform.translation.y, yaw))
            except Exception:
                pass
        spin(3.0)
        result = {"mode": args.mode, "stamp": args.stamp, "slam_params": args.slam_param, "bag": str(bag), "map_to_odom_samples": samples}
        if scan_stats:
            ss = np.array(scan_stats); frac = ss[:, 1] / ss[:, 0]
            result["scan_stats"] = {"scans": int(len(ss)), "beams": int(ss[0, 0]), "valid_median": int(np.median(ss[:, 1])), "valid_fraction_median": round(float(np.median(frac)), 3),
                                    "valid_fraction_p5": round(float(np.percentile(frac, 5)), 3)}
        try:
            t = buf.lookup_transform("map", "odom", rclpy.time.Time()); q = t.transform.rotation
            result["map_to_odom_at_save"] = {"x": t.transform.translation.x, "y": t.transform.translation.y, "z": t.transform.translation.z, "quat_xyzw": [q.x, q.y, q.z, q.w]}
        except Exception as e:
            result["map_to_odom_at_save"] = "unavailable: %s" % e
        if first_pose:
            m = first_pose[0]; p, q = m.pose.pose.position, m.pose.pose.orientation
            core = bridge.OdomFromMapper((0.191, 0.02329, 0.15588))
            r0 = bridge.quat_to_mat((q.x, q.y, q.z, q.w)); o = (0.191, 0.02329, 0.15588)
            ro = [sum(r0[i][k] * o[k] for k in range(3)) for i in range(3)]
            result["camera_init_to_odom"] = {"xyz": [p.x - ro[0], p.y - ro[1], p.z - ro[2]], "quat_xyzw": [q.x, q.y, q.z, q.w],
                                              "note": "odom is the base pose at startup, so this is the base pose at startup in the mapper frame camera_init (P0 * Tb^-1)"}
        if args.mode in ("map", "scanonly"):
            graph = out / "map/session"; (out / "map").mkdir(exist_ok=True)
            rc = subprocess.run(["ros2", "service", "call", "/slam_toolbox/serialize_map", "slam_toolbox/srv/SerializePoseGraph", "{filename: '%s'}" % graph],
                                capture_output=True, text=True, timeout=60)
            result["serialize"] = rc.stdout.strip()[-200:] or rc.stderr.strip()[-200:]
            rc = subprocess.run(["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", str(out / "map/map"), "--ros-args", "-p", "save_map_timeout:=10.0"],
                                capture_output=True, text=True, timeout=60)
            result["map_saver"] = (rc.stdout + rc.stderr).strip()[-200:]
            pts = pcd_from_bag(bag)
            if len(pts):
                raw_count = len(pts); keys = np.floor(pts / 0.05).astype(np.int64)
                _, idx = np.unique(keys, axis=0, return_index=True); pts = pts[idx].astype("<f4")
                header = ("# .PCD v0.7 - Point Cloud Data file format\nVERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\nWIDTH %d\nHEIGHT 1\n"
                          "VIEWPOINT 0 0 0 1 0 0 0\nPOINTS %d\nDATA binary\n" % (len(pts), len(pts)))
                (out / "map/cloud_registered.pcd").write_bytes(header.encode() + pts.tobytes())
                result["pcd"] = {"points": int(len(pts)), "raw_points": int(raw_count), "voxel_m": 0.05, "frame": "camera_init", "source": "bag /cloud_registered, not a mapper pcd_save"}
        (out / "result.json").write_text(json.dumps(result, indent=1))
        if samples:
            print("map -> odom samples: %d, first %s, last %s" % (len(samples), tuple(round(v, 3) for v in samples[0]), tuple(round(v, 3) for v in samples[-1])))
        print("wrote", out / "result.json")
    finally:
        for p in reversed(procs):
            stop(p)
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == "__main__":
    main()
