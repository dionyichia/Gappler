"""Known synthetic Livox-layout clouds through relay/converter; no hardware."""
import ast
import copy
from contextlib import ExitStack
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
PROFILES = {
    "slam_mapping": "nav/robot_slam/launch/slam_mapping.launch.py",
    "slam_localization": "nav/robot_slam/launch/slam_localization.launch.py",
    "navigation": "nav/robot_navigation/launch/navigation.launch.py",
}


def _converter_node(profile: str):
    tree = ast.parse((REPO / PROFILES[profile]).read_text())
    node = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Assign) and
                any(isinstance(target, ast.Name) and target.id == "pointcloud_to_laserscan" for target in node.targets))
    return tree, node


def converter_parameters(profile: str) -> dict:
    """Read the owned launch's literal converter parameters rather than duplicate them."""
    _, node = _converter_node(profile)
    parameters = next(keyword.value for keyword in node.keywords if keyword.arg == "parameters")
    return ast.literal_eval(parameters)[0]


def converter_routes(profile: str) -> tuple:
    """Require the real returned converter/relay actions and supported source wiring."""
    tree, node = _converter_node(profile)
    description = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                       isinstance(node.func, ast.Name) and node.func.id == "LaunchDescription")
    actions = {node.id for node in description.args[0].elts if isinstance(node, ast.Name)}
    if "pointcloud_to_laserscan" not in actions:
        raise ValueError("converter constructed but not returned")
    remappings = ast.literal_eval(next(keyword.value for keyword in node.keywords if keyword.arg == "remappings"))
    routes = {key.lstrip("/"): value for key, value in remappings}
    cloud = routes.get("cloud_in", "/cloud_in")
    if cloud not in ("/cloud_relay", "/livox/lidar"):
        raise ValueError(f"unsupported input route: {cloud}")
    if cloud == "/cloud_relay" and "qos_relay_node" not in actions:
        raise ValueError("relay route selected but relay not returned")
    return cloud, routes.get("scan", "/scan")


def relay_qos_contract() -> dict:
    """Inspect declared profiles and their actual constructor use; DDS omits depth/history."""
    tree = ast.parse((REPO / "nav/qos_relay/qos_relay.py").read_text())
    profiles = {}
    for name in ("RELIABLE_QOS", "BEST_EFFORT_QOS"):
        expression = next(node.value for node in tree.body if isinstance(node, ast.Assign) and
                          any(isinstance(target, ast.Name) and target.id == name for target in node.targets))
        profiles[name] = {keyword.arg: keyword.value.attr if isinstance(keyword.value, ast.Attribute)
                          else ast.literal_eval(keyword.value) for keyword in expression.keywords}
    relay = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "QoSRelay")
    for method, index, profile in (("create_publisher", 2, "BEST_EFFORT_QOS"), ("create_subscription", 3, "RELIABLE_QOS")):
        call = next(node for node in ast.walk(relay) if isinstance(node, ast.Call) and
                    isinstance(node.func, ast.Attribute) and node.func.attr == method)
        if not isinstance(call.args[index], ast.Name) or call.args[index].id != profile:
            raise ValueError(f"relay constructor no longer uses {profile} for {method}")
    return {"input": profiles["RELIABLE_QOS"], "output": profiles["BEST_EFFORT_QOS"]}


def cloud_bytes(points: list) -> bytes:
    """Match the existing bench's 26-byte little-endian Livox PointXYZRTLT layout."""
    return b"".join(struct.pack("<ffffBBd", x, y, z, 1.0, 0, 0, 0.0) for x, y, z in points)


def expected_bins(points: list, params: dict) -> dict:
    """Independent geometric oracle: nearest valid horizontal range per angular bin."""
    bins = {}
    for x, y, z in points:
        if not all(math.isfinite(value) for value in (x, y, z)):
            continue
        radius, angle = math.hypot(x, y), math.atan2(y, x)
        if not (params["min_height"] <= z <= params["max_height"] and
                params["range_min"] <= radius <= params["range_max"] and
                params["angle_min"] <= angle < params["angle_max"]):
            continue
        index = int((angle - params["angle_min"]) / params["angle_increment"])
        bins[index] = min(bins.get(index, math.inf), radius)
    return bins


def main() -> None:
    if sys.flags.optimize or os.environ.get("ROS_DOMAIN_ID") != "127" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise RuntimeError("REFUSED: unoptimized Python, domain 127 and localhost-only required")
    try:
        import rclpy
        from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
        from rclpy.signals import SignalHandlerOptions
        from sensor_msgs.msg import LaserScan, PointCloud2, PointField
        from gappler_common import config
        from test_velocity_smoother import stop_process
    except ImportError as error:
        print(f"SKIP: cloud/scan dependencies unavailable: {error}")
        sys.exit(3)
    prefix = subprocess.run(["ros2", "pkg", "prefix", "pointcloud_to_laserscan"], capture_output=True, text=True)
    if prefix.returncode:
        print(f"SKIP: pointcloud_to_laserscan unavailable: {prefix.stderr.strip()}")
        sys.exit(3)
    subprocess.run([sys.executable, str(REPO / "bench/t34_guard.py")], check=True)
    topics = config("nav")["topics"]
    declared = relay_qos_contract()
    for role, reliability in (("input", "RELIABLE"), ("output", "BEST_EFFORT")):
        assert declared[role] == {"reliability": reliability, "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10}
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node("t35_cloud_scan_probe", namespace="/t35_scan")
    best_effort = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
    publisher = node.create_publisher(PointCloud2, "/t35_scan/input", 10)
    clouds, scans = [], []
    node.create_subscription(PointCloud2, "/t35_scan/relayed", clouds.append, best_effort)
    node.create_subscription(LaserScan, "/t35_scan/scan", scans.append, best_effort)
    processes = []

    def spin_for(seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.01)

    def stamp(message):
        return message.header.stamp.sec, message.header.stamp.nanosec

    def polar(radius, angle, height):
        return radius * math.cos(angle), radius * math.sin(angle), height

    try:
        spin_for(1)
        if set(node.get_node_names()) != {node.get_name()}:
            raise RuntimeError("REFUSED: domain became occupied")
        with ExitStack() as logs:
            def start(arguments, name):
                log = logs.enter_context((REPO / "log" / f"t35-{name}.log").open("w"))
                process = subprocess.Popen(arguments, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                processes.append(process)
                return process

            relay = start([
                sys.executable, str(REPO / "nav/qos_relay/qos_relay.py"), "--ros-args", "-r", "__ns:=/t35_scan",
                "-r", f"{topics['livox_lidar']}:=/t35_scan/input", "-r", f"{topics['cloud_relay']}:=/t35_scan/relayed",
            ], "relay")
            for profile in PROFILES:
                params = converter_parameters(profile)
                input_topic, output_topic = converter_routes(profile)
                if input_topic not in (topics["cloud_relay"], topics["livox_lidar"]):
                    raise RuntimeError("launch input and owned topic config disagree")
                through_relay = input_topic == topics["cloud_relay"]
                arguments = ["ros2", "run", "pointcloud_to_laserscan", "pointcloud_to_laserscan_node", "--ros-args",
                             "-r", "__ns:=/t35_scan", "-r", f"cloud_in:={'relayed' if through_relay else 'input'}", "-r", "scan:=scan"]
                for key, value in params.items():
                    arguments += ["-p", f"{key}:={str(value).lower() if isinstance(value, bool) else value}"]
                converter = start(arguments, profile)
                try:
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        spin_for(0.1)
                        if (publisher.get_subscription_count() == (1 if through_relay else 2) and
                                node.count_subscribers("/t35_scan/relayed") == (2 if through_relay else 1) and
                                node.count_publishers("/t35_scan/scan") == 1):
                            break
                    else:
                        raise RuntimeError(f"{profile}: cloud/scan connections not ready")
                    assert relay.poll() is None and converter.poll() is None
                    info = node.get_publishers_info_by_topic("/t35_scan/relayed")
                    inputs = [info for info in node.get_subscriptions_info_by_topic("/t35_scan/input") if info.node_name == "qos_relay"]
                    assert len(info) == 1 and len(inputs) == 1
                    for endpoint, reliability in ((info[0], ReliabilityPolicy.BEST_EFFORT), (inputs[0], ReliabilityPolicy.RELIABLE)):
                        qos = endpoint.qos_profile
                        assert qos.reliability == reliability and qos.durability == DurabilityPolicy.VOLATILE
                        # Fast DDS graph discovery on this box reports UNKNOWN/0.
                        # Assert known endpoint values; declaration/use is checked above.
                        assert qos.history in (HistoryPolicy.UNKNOWN, HistoryPolicy.KEEP_LAST)
                        assert qos.depth in (0, 10)
                    print(f"PASS {profile}: relay input/output reliability+durability; declared history/depth checked", flush=True)
                    assert node.count_publishers("/t35_scan/input") == 1
                    height = (params["min_height"] + params["max_height"]) / 2
                    cases = {
                        "known_geometry": [(2, 0, height), (4, 0, height), (0, 3, height), (0, -1.5, height),
                                           polar(2.5, 0.7, height)],
                        "bounds": [polar(2, 0.7, params["min_height"] + 0.01),
                                   polar(3, -0.7, params["max_height"] - 0.01),
                                   polar(1, 1.1, params["min_height"] - 0.01),
                                   polar(1, 1.3, params["max_height"] + 0.01),
                                   polar(params["range_min"] + 0.05, 1.5, height),
                                   polar(params["range_min"] * 0.5, 1.7, height),
                                   polar(params["range_max"] - 0.05, 2.1, height),
                                   polar(params["range_max"] + 0.05, 2.3, height)],
                        "invalid_only": [(math.nan, 1, height), (1, math.nan, height), (1, 1, math.nan),
                                         (math.inf, 1, height), (1, 1, params["max_height"] + 1)],
                        "empty": [],
                    }
                    for label, points in cases.items():
                        clouds.clear()
                        scans.clear()
                        message = PointCloud2()
                        message.header.frame_id = "livox_frame"
                        message.height, message.width, message.point_step = 1, len(points), 26
                        message.row_step = message.width * message.point_step
                        message.is_dense = False
                        message.is_bigendian = False
                        message.fields = [PointField(name=name, offset=offset, datatype=datatype, count=1)
                                          for name, offset, datatype in (("x", 0, PointField.FLOAT32), ("y", 4, PointField.FLOAT32),
                                          ("z", 8, PointField.FLOAT32), ("intensity", 12, PointField.FLOAT32),
                                          ("tag", 16, PointField.UINT8), ("line", 17, PointField.UINT8), ("timestamp", 18, PointField.FLOAT64))]
                        message.data = cloud_bytes(points)
                        encoded = [struct.unpack_from("<fff", message.data, offset) for offset in range(0, len(message.data), 26)]
                        expected = expected_bins(encoded, params)
                        sent = {}
                        for _ in range(10):
                            message.header.stamp = node.get_clock().now().to_msg()
                            sent[stamp(message)] = copy.deepcopy(message)
                            publisher.publish(message)
                            spin_for(0.1)
                        spin_for(0.3)
                        received_clouds = [cloud for cloud in clouds if stamp(cloud) in sent]
                        received_scans = [scan for scan in scans if stamp(scan) in sent]
                        cloud_stamps = {stamp(cloud) for cloud in received_clouds}
                        scan_stamps = {stamp(scan) for scan in received_scans}
                        assert len(cloud_stamps) >= 9 and len(cloud_stamps) == len(received_clouds), f"{profile}/{label}: missing/duplicate relay frames"
                        assert len(scan_stamps) >= 9 and len(scan_stamps) == len(received_scans), f"{profile}/{label}: missing/duplicate scans"
                        for cloud in received_clouds:
                            assert cloud == sent[stamp(cloud)], "relay changed PointCloud2 payload/metadata"
                        for scan in received_scans:
                            assert scan.header.frame_id == params["target_frame"]
                            for name in ("angle_min", "angle_max", "angle_increment", "scan_time", "range_min", "range_max"):
                                assert math.isclose(getattr(scan, name), params[name], rel_tol=1e-6, abs_tol=1e-6), name
                            size = math.ceil((params["angle_max"] - params["angle_min"]) / params["angle_increment"])
                            assert len(scan.ranges) == size
                            finite = {index: value for index, value in enumerate(scan.ranges) if math.isfinite(value)}
                            assert finite.keys() == expected.keys(), f"{profile}/{label}: wrong occupied bins {finite.keys()} != {expected.keys()}"
                            for index, radius in expected.items():
                                assert math.isclose(finite[index], radius, rel_tol=1e-5, abs_tol=1e-5), f"wrong range at bin {index}"
                            assert all(math.isinf(value) and value > 0 for index, value in enumerate(scan.ranges) if index not in expected)
                        print(f"PASS {profile}/{label}: {len(received_scans)}/10 scans; {len(expected)} occupied bins; "
                              f"{'relay' if through_relay else 'direct'} route ({input_topic} → {output_topic})", flush=True)
                finally:
                    stop_process(converter)
                    processes.remove(converter)
                    spin_for(0.5)
    finally:
        for process in reversed(processes):
            stop_process(process)
        node.destroy_node()
        rclpy.try_shutdown()
    subprocess.run([sys.executable, str(REPO / "bench/t34_guard.py")], check=True)
    print("PASS: synthetic geometry/filtering only; live LiDAR, TF alignment and obstacle safety NOT proven")


if __name__ == "__main__":
    main()
