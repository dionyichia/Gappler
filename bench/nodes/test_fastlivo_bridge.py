"""Option 2 runtime check: the real bridge and converter fed the recorded handdriven1 odometry and LiDAR.

No hardware, no mapper, no Docker, no robot command. Domain 127, localhost only (bench/t34_guard.py checks it is empty).
Passes when: exactly one node publishes /tf and it is fastlivo_odom_bridge; the only edge is odom -> robot_base_link at at one
final pose per scan (about 10.6 Hz from the recorded 20 Hz, two poses per scan); /cloud_relay arrives at about 10 Hz with the full cloud; the bridge stops publishing when the player stops; and a
second, deliberately added TF publisher (negative control) IS caught by the same ownership check.
Exit 0 pass, 1 fail, 3 skipped (no ROS, numpy or bag).
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
BAG = os.environ.get("BENCH_FASTLIVO_BAG", "/home/rcp2026/rcp-Gappler/log/t59-fastlivo/log/t35d-attended-20261020.raLTgE/run/bag/handdriven1")
# the bag has 2 poses per scan at 20 Hz; the bridge publishes the final one per scan: 10 Hz plus about 6% extra (scans with 3 poses)
EXPECTED_ODOM_HZ, EXPECTED_CLOUD_HZ = 10.6, 10.0
STUB_TF_PUBLISHER = """
import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
rclpy.init()
n = Node("stub_wheel_driver")
b = TransformBroadcaster(n)
def tick():
    t = TransformStamped(); t.header.stamp = n.get_clock().now().to_msg()
    t.header.frame_id, t.child_frame_id = "odom", "robot_base_link"; t.transform.rotation.w = 1.0
    b.sendTransform(t)
n.create_timer(1 / 30, tick)
rclpy.spin(n)
"""


def skip(reason):
    print("SKIP: " + reason)
    sys.exit(3)


def start(cmd, log):
    return subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT, start_new_session=True, cwd=REPO)


def stop(proc):
    if proc is None or proc.poll() is not None:
        return
    for sig, wait in ((signal.SIGINT, 5), (signal.SIGTERM, 3), (signal.SIGKILL, 2)):
        try:
            os.killpg(proc.pid, sig)
            proc.wait(wait)
            return
        except (subprocess.TimeoutExpired, ProcessLookupError):
            continue


def main():
    try:
        import numpy  # noqa: F401
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
        from sensor_msgs.msg import PointCloud2
        from tf2_msgs.msg import TFMessage
    except ImportError as error:
        skip("ROS 2 Humble and numpy are needed: %s" % error)
    if not (Path(BAG) / "metadata.yaml").is_file():
        skip("bag not found (set BENCH_FASTLIVO_BAG): %s" % BAG)

    folder = Path(tempfile.mkdtemp(prefix="fastlivo_bridge_bench_"))
    (folder / "qos.yaml").write_text("".join(
        "%s:\n  history: keep_last\n  depth: 10\n  reliability: reliable\n  durability: volatile\n" % t for t in ("/livox/lidar", "/aft_mapped_to_init")))
    procs = []
    failures = []
    rclpy.init()
    node = Node("fastlivo_bridge_bench_watch")
    edges, clouds, tf_times = {}, [], []

    def on_tf(msg):
        for t in msg.transforms:
            edges.setdefault((t.header.frame_id, t.child_frame_id), []).append((time.monotonic(), t))
        tf_times.append(time.monotonic())

    qos = lambda rel: QoSProfile(reliability=rel, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=200)
    node.create_subscription(TFMessage, "/tf", on_tf, qos(ReliabilityPolicy.RELIABLE))
    node.create_subscription(PointCloud2, "/cloud_relay", lambda m: clouds.append((time.monotonic(), m.width, m.header.frame_id, [f.name for f in m.fields])), qos(ReliabilityPolicy.BEST_EFFORT))

    def spin(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.02)

    def tf_publishers():
        return sorted(i.node_name for i in node.get_publishers_info_by_topic("/tf") if i.node_name != node.get_name())

    try:
        procs.append(start([sys.executable, "nav/robot_slam/scripts/fastlivo_odom_bridge.py", "--ros-args", "--params-file", "nav/robot_slam/config/fastlivo_bridge.yaml"], folder / "bridge.log"))
        procs.append(start([sys.executable, "nav/robot_slam/scripts/livox_custom_to_cloud.py"], folder / "converter.log"))
        spin(4.0)
        player = start(["ros2", "bag", "play", BAG, "--topics", "/aft_mapped_to_init", "/livox/lidar", "--qos-profile-overrides-path", str(folder / "qos.yaml")], folder / "player.log")
        procs.append(player)
        spin(6.0)  # warm-up
        edges.clear(); clouds.clear()
        t0 = time.monotonic()
        spin(12.0)
        window = time.monotonic() - t0

        owners = tf_publishers()
        if owners != ["fastlivo_odom_bridge"]:
            failures.append("TF publishers should be exactly [fastlivo_odom_bridge], got %s" % owners)
        if set(edges) != {("odom", "robot_base_link")}:
            failures.append("TF edges should be exactly odom -> robot_base_link, got %s" % sorted(edges))
        odom_hz = len(edges.get(("odom", "robot_base_link"), [])) / window
        cloud_hz = len(clouds) / window
        if abs(odom_hz - EXPECTED_ODOM_HZ) > 1.3:
            failures.append("odom -> robot_base_link rate %.1f Hz, expected about %.0f" % (odom_hz, EXPECTED_ODOM_HZ))
        if abs(cloud_hz - EXPECTED_CLOUD_HZ) > 1.5:
            failures.append("/cloud_relay rate %.1f Hz, expected about %.0f" % (cloud_hz, EXPECTED_CLOUD_HZ))
        if not clouds or min(c[1] for c in clouds) < 10000 or {c[2] for c in clouds} != {"livox_frame"} or clouds[0][3] != ["x", "y", "z", "intensity"]:
            failures.append("clouds should be full x y z intensity clouds in livox_frame: %s" % (clouds[:1],))
        zs = [abs(t.transform.translation.z) for _, t in edges.get(("odom", "robot_base_link"), [])]
        if zs and max(zs) > 0.5:
            failures.append("base z left the floor: %.2f m" % max(zs))
        print("measured over %.1f s: odom -> robot_base_link %.1f Hz (publishers %s), /cloud_relay %.1f Hz, %d points per cloud, max |z| %.3f m" % (
            window, odom_hz, owners, cloud_hz, clouds[-1][1] if clouds else 0, max(zs) if zs else float("nan")))

        # the bridge must go quiet when the mapper output stops
        stop(player)
        stopped = time.monotonic()
        spin(1.5)
        late = [t for t in tf_times if t > stopped + 0.3]
        if late:
            failures.append("bridge kept publishing %d TF messages more than 0.3 s after the mapper output stopped" % len(late))
        spin(0.5)
        if "publishing nothing on odom" not in (folder / "bridge.log").read_text():
            failures.append("bridge did not report the stale mapper output")
        print("stale stop: %d TF messages after the player stopped" % len(late))

        # negative control: a second TF publisher must be caught by the same ownership check
        procs.append(start([sys.executable, "-c", STUB_TF_PUBLISHER], folder / "stub.log"))
        spin(3.0)
        control = tf_publishers()
        caught = control != ["fastlivo_odom_bridge"]
        print("negative control: TF publishers now %s -> %s" % (control, "caught" if caught else "NOT CAUGHT"))
        if not caught:
            failures.append("negative control failed: a second TF publisher was not seen, the ownership check is vacuous")
    finally:
        for proc in reversed(procs):
            stop(proc)
        node.destroy_node()
        rclpy.try_shutdown()
    for line in failures:
        print("FAIL: " + line)
    print("logs in %s" % folder)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
