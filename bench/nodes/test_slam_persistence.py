"""Installed SLAM mapping/save/restart/localization with synthetic scans only."""
import math
import json
import signal
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
# Asymmetric room plus an internal segment avoids a featureless symmetric box.
WALLS = ((-3, -2, 5, -2), (5, -2, 5, 4), (5, 4, -3, 4),
         (-3, 4, -3, -2), (2, 0.5, 2, 2.5))


def ray_range(x: float, y: float, angle: float) -> float:
    """Nearest positive ray/segment intersection in metres."""
    dx, dy = math.cos(angle), math.sin(angle)
    distance = 20.0
    for ax, ay, bx, by in WALLS:
        sx, sy = bx - ax, by - ay
        determinant = dx * sy - dy * sx
        if abs(determinant) < 1e-12:
            continue
        qx, qy = ax - x, ay - y
        along_ray = (qx * sy - qy * sx) / determinant
        along_segment = (qx * dy - qy * dx) / determinant
        if along_ray > 0 and 0 <= along_segment <= 1:
            distance = min(distance, along_ray)
    return distance


def scan_ranges(pose: tuple, count: int = 720) -> list:
    """Full circular scan starting at forward, with no duplicated endpoint."""
    x, y, heading = pose
    return [ray_range(x, y, heading + i * 2 * math.pi / count) for i in range(count)]


def pose_error(actual: tuple, expected: tuple) -> tuple:
    """Position error and shortest absolute heading difference."""
    difference = actual[2] - expected[2]
    return math.hypot(actual[0] - expected[0], actual[1] - expected[1]), abs(math.atan2(math.sin(difference), math.cos(difference)))


def await_startup(child, ready, spin_for, stop):
    """Own the child until readiness succeeds, including interrupted startup."""
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            spin_for(0.1)
            if child.poll() is not None:
                raise RuntimeError("SLAM exited during startup; inspect its log")
            if ready():
                return child
        raise RuntimeError("SLAM scan subscription unavailable")
    except BaseException:
        # KeyboardInterrupt must clean up a child in its separate process group.
        stop(child)
        raise


def main() -> None:
    if sys.flags.optimize or os.environ.get("ROS_DOMAIN_ID") != "127" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise RuntimeError("REFUSED: unoptimized Python/domain127/localhost required")
    try:
        import rclpy
        from rclpy.signals import SignalHandlerOptions
        from geometry_msgs.msg import TransformStamped, PoseWithCovarianceStamped
        from nav_msgs.srv import GetMap
        from nav_msgs.msg import OccupancyGrid
        from rcl_interfaces.srv import GetParameters
        from rclpy.qos import QoSProfile, DurabilityPolicy
        from sensor_msgs.msg import LaserScan
        from slam_toolbox.srv import SerializePoseGraph, DeserializePoseGraph
        from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
        import yaml
        from test_velocity_smoother import stop_process
    except ImportError as error:
        print(f"SKIP: {error}")
        sys.exit(3)
    available = subprocess.run(["ros2", "pkg", "prefix", "slam_toolbox"], capture_output=True, text=True)
    if available.returncode:
        print(f"SKIP: slam_toolbox unavailable: {available.stderr.strip()}")
        sys.exit(3)
    subprocess.run([sys.executable, str(REPO / "bench/t34_guard.py")], check=True)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    remaps = ["--ros-args", "-r", "/tf:=/t35_slam/tf", "-r", "/tf_static:=/t35_slam/tf_static"]
    node = rclpy.create_node("persistence_probe", namespace="/t35_slam", cli_args=remaps)
    publisher = node.create_publisher(LaserScan, "/t35_slam/scan", 10)
    dynamic = TransformBroadcaster(node)
    static = StaticTransformBroadcaster(node)
    poses = []
    node.create_subscription(PoseWithCovarianceStamped, "/t35_slam/pose", poses.append, 10)
    # updateMap skips rasterization without subscribers. Do not depend on a
    # previous saver/subscriber remaining visible across process restart.
    maps = []
    map_subscription = node.create_subscription(OccupancyGrid, "/t35_slam/map", maps.append,
                                                QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
    process = None

    def spin_for(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.01)

    def call(service, kind, request, timeout=15):
        client = node.create_client(kind, "/t35_slam/slam_toolbox/" + service)
        try:
            if not client.wait_for_service(timeout_sec=8):
                raise RuntimeError(f"missing service: {service}")
            future = client.call_async(request)
            rclpy.spin_until_future_complete(node, future, timeout_sec=timeout)
            if not future.done() or future.result() is None:
                raise RuntimeError(f"service did not complete: {service}")
            return future.result()
        finally:
            node.destroy_client(client)

    def wait_departed():
        """Do not mistake stale DDS discovery for a newly restarted localizer."""
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            spin_for(0.1)
            if ("slam_toolbox", "/t35_slam") not in node.get_node_names_and_namespaces():
                return
        raise RuntimeError("stopped SLAM node remains visible; refuse ambiguous restart")

    def feed(pose, bias=(0, 0, 0), repeats=6):
        sent = set()
        for _ in range(repeats):
            stamp = node.get_clock().now().to_msg()
            transform = TransformStamped()
            transform.header.stamp = stamp
            transform.header.frame_id, transform.child_frame_id = "t35_odom", "t35_base"
            transform.transform.translation.x = float(pose[0] + bias[0])
            transform.transform.translation.y = float(pose[1] + bias[1])
            angle = pose[2] + bias[2]
            transform.transform.rotation.z, transform.transform.rotation.w = math.sin(angle / 2), math.cos(angle / 2)
            dynamic.sendTransform(transform)
            scan = LaserScan()
            scan.header.stamp, scan.header.frame_id = stamp, "t35_laser"
            scan.angle_min = 0.0
            scan.angle_increment = 2 * math.pi / 720
            scan.angle_max = 719 * scan.angle_increment
            scan.range_min, scan.range_max, scan.scan_time = 0.1, 20.0, 0.1
            scan.ranges = scan_ranges(pose)
            publisher.publish(scan)
            sent.add((stamp.sec, stamp.nanosec))
            spin_for(0.1)
        return sent

    try:
        spin_for(1)
        if set(node.get_node_names()) != {node.get_name()}:
            raise RuntimeError("REFUSED: domain became occupied")
        transform = TransformStamped()
        transform.header.stamp = node.get_clock().now().to_msg()
        transform.header.frame_id, transform.child_frame_id = "t35_base", "t35_laser"
        transform.transform.rotation.w = 1.0
        static.sendTransform(transform)
        with tempfile.TemporaryDirectory(prefix="slam persistence with spaces ", dir=REPO / "log") as directory:
            folder = Path(directory)
            graph = folder / "completed_map"

            def start(executable, mode):
                params = yaml.safe_load((REPO / "nav/robot_slam/config/slam_toolbox.yaml").read_text())["slam_toolbox"]["ros__parameters"]
                params.update(mode=mode, odom_frame="t35_odom", map_frame="t35_map", base_frame="t35_base",
                              scan_topic="/t35_slam/scan", map_name="/t35_slam/map", map_update_interval=0.2,
                              use_sim_time=False, map_file_name="", use_map_saver=False)
                file = folder / (mode + ".yaml")
                file.write_text(yaml.safe_dump({"/**": {"ros__parameters": params}}))
                with (REPO / "log" / ("t35-slam-" + mode + ".log")).open("w") as output:
                    child = subprocess.Popen(["ros2", "run", "slam_toolbox", executable, *remaps,
                                              "-r", "__ns:=/t35_slam", "--params-file", str(file)],
                                             stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                return await_startup(child, lambda: publisher.get_subscription_count() == 1, spin_for, stop_process)

            process = start("async_slam_toolbox_node", "mapping")
            # Multiple distinct positions, exact odometry; first scan defines map origin.
            trajectory = [(i * 0.1, 0.0, 0.0) for i in range(11)]
            trajectory += [(1.0, i * 0.1, 0.0) for i in range(1, 11)]
            trajectory += [(1.0 - i * 0.1, 1.0, 0.0) for i in range(1, 11)]
            trajectory += [(0.0, 1.0 - i * 0.1, 0.0) for i in range(1, 11)]
            for pose in trajectory:
                feed(pose)
            assert len(poses) >= 15, f"too few mapping pose updates: {len(poses)}"
            spin_for(0.5)
            original = call("dynamic_map", GetMap, GetMap.Request()).map
            assert original.info.width > 0 and original.info.height > 0
            node.destroy_subscription(map_subscription)
            deadline = time.monotonic() + 10
            while node.count_subscribers("/t35_slam/map") and time.monotonic() < deadline:
                spin_for(0.1)
            assert node.count_subscribers("/t35_slam/map") == 0
            # Advance graph while nobody subscribes: cached raster is now stale.
            fresh_stamps = feed((0.2, -0.5, 0.0), repeats=10)
            # Exercise the actual owned saver, not a duplicated service sequence.
            snapshot_root = folder / "owned snapshots with spaces"
            saver_log = REPO / "log/t35-owned-map-saver.log"
            with saver_log.open("w") as output:
                owned_saver = subprocess.Popen([
                    sys.executable, str(REPO / "nav/robot_slam/scripts/save_slam_map.py"),
                    "--output-root", str(snapshot_root), "--namespace", "/t35_slam",
                    "--map-topic", "/t35_slam/map", "--stationary",
                ], stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    deadline = time.monotonic() + 50
                    while owned_saver.poll() is None and time.monotonic() < deadline:
                        spin_for(0.1)
                    assert owned_saver.poll() == 0, "owned saver failed; inspect log/t35-owned-map-saver.log"
                finally:
                    stop_process(owned_saver)
            snapshots = list(snapshot_root.glob("session-*"))
            assert len(snapshots) == 1
            owned_snapshot = snapshots[0]
            assert "SAVED_SNAPSHOT=" + str(owned_snapshot) in saver_log.read_text()
            assert (owned_snapshot / "manifest.json").is_file()
            manifest = json.loads((owned_snapshot / "manifest.json").read_text())
            assert tuple(manifest["map_stamp"]) in fresh_stamps, "saver captured stale cached raster"
            original = call("dynamic_map", GetMap, GetMap.Request()).map
            # Restore a probe subscription for the independent persistence checks.
            node.create_subscription(OccupancyGrid, "/t35_slam/map", maps.append,
                                     QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
            # Verify the saver restored mapping rather than silently leaving it paused.
            sent = feed((0.3, 0.0, 0.0), repeats=10)
            assert any((pose.header.stamp.sec, pose.header.stamp.nanosec) in sent for pose in poses), "owned saver left mapper unable to process fresh scans"
            print("PASS owned saver: new graph/image snapshot, manifest, spaces, mapper resumed", flush=True)
            pause_request = GetParameters.Request()
            pause_request.names = ["paused_new_measurements"]
            for label, interruption in (("sigint", signal.SIGINT), ("sigterm", signal.SIGTERM)):
                interrupted_root = folder / ("interrupted-" + label)
                with (REPO / "log" / ("t35-owned-saver-" + label + ".log")).open("w") as output:
                    interrupted_saver = subprocess.Popen([
                        sys.executable, str(REPO / "nav/robot_slam/scripts/save_slam_map.py"),
                        "--output-root", str(interrupted_root), "--namespace", "/t35_slam",
                        "--map-topic", "/t35_slam/map", "--stationary",
                    ], stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                    try:
                        deadline = time.monotonic() + 10
                        while time.monotonic() < deadline:
                            assert interrupted_saver.poll() is None, "saver exited before interruption"
                            if call("get_parameters", GetParameters, pause_request).values[0].bool_value:
                                break
                            spin_for(0.02)
                        else:
                            raise RuntimeError("never observed saver pause for interruption test")
                        os.killpg(interrupted_saver.pid, interruption)
                        assert interrupted_saver.wait(timeout=30) != 0
                    finally:
                        stop_process(interrupted_saver)
                assert not call("get_parameters", GetParameters, pause_request).values[0].bool_value
                assert "SAVED_SNAPSHOT=" not in (REPO / "log" / ("t35-owned-saver-" + label + ".log")).read_text()
                sent = feed((0.5 if label == "sigint" else 0.7, 0.0, 0.0), repeats=10)
                assert any((pose.header.stamp.sec, pose.header.stamp.nanosec) in sent for pose in poses)
                print(f"PASS owned saver {label}: interrupted after pause, mapper restored and fresh scans processed", flush=True)
            request = SerializePoseGraph.Request()
            request.filename = str(graph)
            response = call("serialize_map", SerializePoseGraph, request)
            assert response.result == response.RESULT_SUCCESS, f"serialize failed: {response.result}"
            for suffix in (".posegraph", ".data"):
                assert Path(str(graph) + suffix).stat().st_size > 0
            print("PASS mapping and real graph serialization", flush=True)
            image = folder / "current_map"
            # Upstream SaveMap shells out with an unquoted filename. Pass argv
            # directly to the installed saver and explicitly choose our private map.
            with (REPO / "log/t35-slam-image-save.log").open("w") as output:
                saver = subprocess.Popen(["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", str(image),
                                          "--ros-args", "-r", "map:=/t35_slam/map", "-p", "save_map_timeout:=5.0",
                                          "-p", "map_subscribe_transient_local:=true"],
                                         stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    assert saver.wait(timeout=15) == 0, "image save failed; inspect log/t35-slam-image-save.log"
                finally:
                    stop_process(saver)
            metadata = yaml.safe_load(Path(str(image) + ".yaml").read_text())
            image_path = Path(metadata["image"])
            image_path = image_path if image_path.is_absolute() else folder / image_path
            assert image_path.is_file() and image_path.stat().st_size > 0
            assert math.isclose(metadata["resolution"], 0.05, abs_tol=1e-6)
            print("PASS image save with YAML/image reference; path contains spaces", flush=True)
            stop_process(process)
            process = None
            wait_departed()
            poses.clear()
            process = start("localization_slam_toolbox_node", "localization")
            # A reply alone cannot distinguish a failed load in this API.
            # Exercise both failures in a fresh node with no scans/map loaded.
            corrupt = folder / "corrupt_map"
            for suffix in (".posegraph", ".data"):
                Path(str(corrupt) + suffix).write_bytes(b"not a serialized graph")
            for label, filename in (("missing", folder / "absent_map"), ("corrupt", corrupt)):
                request = DeserializePoseGraph.Request()
                request.filename = str(filename)
                request.match_type = request.LOCALIZE_AT_POSE
                try:
                    call("deserialize_map", DeserializePoseGraph, request)
                except RuntimeError:
                    if label != "corrupt" or process.poll() is None:
                        raise
                    log = (REPO / "log/t35-slam-localization.log").read_text()
                    assert "std::length_error" in log and "Aborted" in log, "unexpected localizer failure"
                    (REPO / "log/t35-slam-corrupt-load.log").write_text(log)
                    assert not poses
                    print("OBSERVED LIMITATION: corrupt graph aborts installed localizer (std::length_error); NOT safe rejection", flush=True)
                    stop_process(process)
                    process = None
                    wait_departed()
                    process = start("localization_slam_toolbox_node", "localization")
                    continue
                unloaded = call("dynamic_map", GetMap, GetMap.Request()).map
                assert unloaded.info.width == 0 and unloaded.info.height == 0
                assert not poses and process.poll() is None
                print(f"PASS {label} load: service replies but no usable map; no success claim", flush=True)
            request = DeserializePoseGraph.Request()
            request.filename = str(owned_snapshot / "completed_map")
            request.match_type = request.LOCALIZE_AT_POSE
            request.initial_pose.x, request.initial_pose.y, request.initial_pose.theta = 0.9, 0.5, 0.25
            call("deserialize_map", DeserializePoseGraph, request)
            # Empty deserialize response is not success evidence: inspect loaded map.
            loaded = call("dynamic_map", GetMap, GetMap.Request()).map
            assert loaded.info.width > 50 and loaded.info.height > 50
            assert any(value == 100 for value in loaded.data) and any(value == 0 for value in loaded.data)
            assert loaded.header.frame_id == "t35_map"
            assert loaded.info == original.info and loaded.data == original.data, "reloaded map differs from saved mapping raster"
            print(f"PASS fresh localization loaded map: {loaded.info.width}x{loaded.info.height}", flush=True)
            for expected in ((0.8, 0.6, 0.2), (0.9, 0.6, 0.2), (1.0, 0.6, 0.2)):
                sent = feed(expected, bias=(0.4, -0.3, 0.1), repeats=10)
                matching = [pose for pose in poses if (pose.header.stamp.sec, pose.header.stamp.nanosec) in sent]
                assert matching, f"no current localization pose at {expected}"
                latest = matching[-1]
                position, rotation = latest.pose.pose.position, latest.pose.pose.orientation
                actual = (position.x, position.y, 2 * math.atan2(rotation.z, rotation.w))
                distance, heading = pose_error(actual, expected)
                assert distance <= 0.15 and heading <= 0.10, f"localization error {distance:.3f}m/{heading:.3f}rad"
                assert latest.header.frame_id == "t35_map"
                print(f"PASS localization: error {distance:.3f}m/{heading:.3f}rad; biased odometry", flush=True)
            # Parameter load path above proves deserialize; now prove /initialpose
            # re-localization without restarting the localizer.
            initialpose_pub = node.create_publisher(PoseWithCovarianceStamped, "/t35_slam/initialpose", 10)
            reseeded = (0.2, 0.3, -0.15)
            seed = PoseWithCovarianceStamped()
            seed.header.frame_id = "t35_map"
            seed.pose.pose.position.x, seed.pose.pose.position.y = reseeded[0], reseeded[1]
            seed.pose.pose.orientation.z = math.sin(reseeded[2] / 2)
            seed.pose.pose.orientation.w = math.cos(reseeded[2] / 2)
            poses.clear()
            for _ in range(5):
                seed.header.stamp = node.get_clock().now().to_msg()
                initialpose_pub.publish(seed)
                spin_for(0.1)
            sent = feed(reseeded, bias=(0.4, -0.3, 0.1), repeats=12)
            matching = [pose for pose in poses if (pose.header.stamp.sec, pose.header.stamp.nanosec) in sent]
            assert matching, "no pose after /initialpose reseeding"
            latest = matching[-1]
            position, rotation = latest.pose.pose.position, latest.pose.pose.orientation
            actual = (position.x, position.y, 2 * math.atan2(rotation.z, rotation.w))
            distance, heading = pose_error(actual, reseeded)
            assert distance <= 0.15 and heading <= 0.10, f"/initialpose error {distance:.3f}m/{heading:.3f}rad"
            node.destroy_publisher(initialpose_pub)
            print(f"PASS /initialpose reseeding: error {distance:.3f}m/{heading:.3f}rad", flush=True)
            refused_root = folder / "must not save localization"
            with (REPO / "log/t35-owned-saver-refusal.log").open("w") as output:
                refused = subprocess.Popen([
                    sys.executable, str(REPO / "nav/robot_slam/scripts/save_slam_map.py"),
                    "--output-root", str(refused_root), "--namespace", "/t35_slam",
                    "--map-topic", "/t35_slam/map", "--stationary",
                ], stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    assert refused.wait(timeout=20) != 0, "saver accepted localization mode"
                finally:
                    stop_process(refused)
            assert not refused_root.exists()
            assert "must be in mapping mode" in (REPO / "log/t35-owned-saver-refusal.log").read_text()
            print("PASS owned saver refuses localization mode before creating snapshot", flush=True)
            stop_process(process)
            process = None
    finally:
        if process is not None:
            stop_process(process)
        node.destroy_node()
        rclpy.try_shutdown()
    subprocess.run([sys.executable, str(REPO / "bench/t34_guard.py")], check=True)
    print("PASS valid synthetic SLAM persistence; corrupt-file abort observed; physical localization NOT proven", flush=True)


if __name__ == "__main__":
    main()
