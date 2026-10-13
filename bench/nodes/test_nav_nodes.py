"""The navigation nodes against synthetic inputs (TESTBENCH_PLAN W7, Phase 5's table).

Run by bench/nav_nodes.sh, which has already proven the ROS channel is private and
empty. Nothing here can drive: there is no Nav2 and no base driver on this channel,
and MockNav2 below -- standing in for Nav2's navigate_to_pose -- only records goals.
Each case starts its node(s) fresh from nav/<package>/
(the files each package's CMakeLists installs), so the nav build is not needed.

  control  approach, far object         camera 0.6 m from object, compensating lateral TF offset
  control  approach, near object        /manipulation/start, no /goal_pose
  control  approach, nav succeeds       bridge -> "success" -> /manipulation/start
  xfail    approach after nav failure   a second object is acted on, after the back-off  F1
  xfail    approach after release       a second object is acted on after a finished cycle  F5
  control  goal bridge, nav aborts      /goal_reached "failed"
  xfail    goal bridge, server down     /goal_reached "failed" within 6 s        F1
  xfail    goal bridge, Nav2 goes away  an accepted goal still ends in "failed"  F1
  xfail    return retry                 a second return reaches Nav2             F2
  xfail    fused pose frame             goal = the fused pose moved into map     E1
  control  QoS relay                    /cloud_relay is BEST_EFFORT, >= 90 % kept  (J4)
  control  robot pose                   /robot_pose ~10 Hz, in map, at the TF pose
  xfail    clean Ctrl+C                 all five nodes exit 0 with no traceback  F4

Controls must pass. An xfail that passes is XPASS: the finding did not reproduce,
retag it. A case whose own setup fails is a FAIL. A case whose node can't import its
dependencies in this Python is a SKIP. Exit 0 = no FAIL, 1 = a FAIL, 3 = all skipped.
"""
import importlib.util
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

try:
    import rclpy
    from rclpy.action import ActionServer, GoalResponse
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from geometry_msgs.msg import PointStamped, PoseStamped, TransformStamped
    from nav2_msgs.action import NavigateToPose
    from sensor_msgs.msg import PointCloud2, PointField
    from std_msgs.msg import Bool, Empty, String
    from tf2_ros import StaticTransformBroadcaster
except ImportError as e:
    print(f"SKIP: {e} -- source ROS 2 Humble first (nav2_msgs is ros-humble-nav2-msgs)")
    sys.exit(3)

REPO = Path(__file__).resolve().parents[2]
NAV = REPO / "nav"   # one package per node since 2026-09-22: nav/<package>/<script>.py
LOG = REPO / os.environ.get("BENCH_NAV_LOG", "log/bench_nav_nodes.txt")
# robot_base_link -> base_link (the arm), as slam_localization.launch.py:102 publishes it
ARM_MOUNT = (0.18, 0.0, 0.48, math.pi)
CAMERA_X, CAMERA_Y = 0.31, -0.06  # deliberately differ from fitted camera: proves TF consumption
CAMERA_FRAME = "base_d455_depth_optical_frame"
APPROACH = 0.6        # object_approach_node.py:55
RETRY_BACKOFF = 3.0   # nav_config.yaml object_approach_node retry_backoff_s
SIDE_OFFSET = 0.6     # goto_glasses.py:33
# modules each script imports beyond rclpy + the message packages checked above
NEEDS = {
    "object_approach_node.py": ["scipy", "tf2_geometry_msgs", "visualization_msgs"],
    "goal_reached_publisher.py": [],
    "goto_glasses.py": ["scipy"],
    "qos_relay.py": [],
    "pose_publisher.py": [],
}
EX = None  # the one executor every bench-side node spins on


class SetupError(Exception):
    """The case could not get to the point of asking its question."""


def spin(sec, until=None):
    end = time.time() + sec
    while time.time() < end:
        EX.spin_once(timeout_sec=0.05)
        if until and until():
            return True
    return bool(until and until())


# ---- messages ------------------------------------------------------------------
def pose(frame, x, y, z=0.0, yaw=0.0):
    m = PoseStamped()
    m.header.frame_id = frame
    m.pose.position.x, m.pose.position.y, m.pose.position.z = float(x), float(y), float(z)
    m.pose.orientation.z, m.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
    return m


def tf(parent, child, x, y, z, yaw):
    t = TransformStamped()
    t.header.frame_id, t.child_frame_id = parent, child
    t.transform.translation.x, t.transform.translation.y, t.transform.translation.z = x, y, z
    t.transform.rotation.z, t.transform.rotation.w = math.sin(yaw / 2), math.cos(yaw / 2)
    return t


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def ang(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def xy(p):
    return f"({p.x:.2f}, {p.y:.2f})"


def in_arm_frame(mx, my, mz):
    """A map point as the perception pipeline would send it: in base_link (the arm), with
    the robot at the map origin. base_link sits at ARM_MOUNT, turned 180 degrees."""
    x0, y0, z0, _ = ARM_MOUNT
    return -(mx - x0), -(my - y0), mz - z0


# ---- the bench's side of the graph -------------------------------------------------
class Rig(Node):
    """One case's publishers, recorders and static TF. Destroyed with the case."""

    def __init__(self, name):
        super().__init__(f"bench_nav_{name}")
        self.got, self.pubs = {}, {}
        self.static = StaticTransformBroadcaster(self)
        EX.add_node(self)

    def listen(self, topic, typ, qos=10):
        self.got[topic] = []
        self.create_subscription(typ, topic, lambda m, t=topic: self.got[t].append((time.time(), m)), qos)

    def pub(self, topic, typ, qos=10):
        self.pubs[topic] = self.create_publisher(typ, topic, qos)

    def send(self, topic, msg):
        self.pubs[topic].publish(msg)

    def since(self, topic, t0):
        return [m for ts, m in self.got[topic] if ts >= t0]

    def close(self):
        EX.remove_node(self)
        self.destroy_node()


class MockNav2(Node):
    """Stands in for Nav2's navigate_to_pose: records every goal, drives nothing.
    mode: 'succeed' (status 4), 'abort' (status 6), 'reject', or 'hang' (accepts the
    goal and never finishes it)."""

    def __init__(self, mode):
        super().__init__("bench_mock_nav2")
        self.mode, self.goals, self.closed = mode, [], False
        # 'hang': an accepted goal is never executed, so it never gets a result
        extra = {"handle_accepted_callback": lambda goal_handle: None} if mode == "hang" else {}
        self.server = ActionServer(self, NavigateToPose, "navigate_to_pose",
                                   execute_callback=self._execute, goal_callback=self._goal, **extra)
        EX.add_node(self)

    def _goal(self, request):
        self.goals.append((time.time(), request.pose))
        return GoalResponse.REJECT if self.mode == "reject" else GoalResponse.ACCEPT

    def _execute(self, goal_handle):
        (goal_handle.succeed if self.mode == "succeed" else goal_handle.abort)()
        return NavigateToPose.Result()

    def close(self):
        if not self.closed:
            self.closed = True
            self.server.destroy()
            EX.remove_node(self)
            self.destroy_node()


class Case:
    """Owns everything one case starts, and stops all of it."""

    def __init__(self, name, log):
        self.rig, self.log, self.procs, self.navs = Rig(name), log, [], []

    def start(self, script, ready_topic, kind="sub", sec=25.0, out=None):
        """Start a node; wait until it shows up on ready_topic (its subscription or
        publisher), then give TF and discovery a moment to settle. out: a file for the
        node's own output instead of the shared log."""
        count = self.rig.count_subscribers if kind == "sub" else self.rig.count_publishers
        base = count(ready_topic)
        self.log.write(f"\n===== {script} =====\n")
        self.log.flush()
        p = subprocess.Popen([sys.executable, str(next(NAV.glob(f"*/{script}")))], stdout=out or self.log,
                             stderr=subprocess.STDOUT, start_new_session=True)
        self.procs.append(p)
        if not spin(sec, lambda: count(ready_topic) > base or p.poll() is not None) or p.poll() is not None:
            raise SetupError(f"{script} did not come up (exit {p.poll()}) -- see {LOG.name}")
        spin(1.5)
        return p

    def nav2(self, mode):
        m = MockNav2(mode)
        self.navs.append(m)
        spin(1.0)
        return m

    def close(self):
        for p in self.procs:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGINT)
                try:
                    p.wait(3)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait(5)
        for m in self.navs:
            m.close()
        self.rig.close()
        spin(1.0)  # let the graph forget this case before the next one


# ---- the cases: each returns (ok, detail) or raises SetupError ----------------------
def approach_rig(c, camera=True):
    r = c.rig
    transforms = [tf("map", "robot_base_link", 0.0, 0.0, 0.0, 0.0),
                  tf("robot_base_link", "base_link", *ARM_MOUNT)]
    if camera:
        transforms.append(tf("robot_base_link", CAMERA_FRAME, CAMERA_X, CAMERA_Y, 0.5425, 0.0))
    r.static.sendTransform(transforms)
    r.pub("/manipulation/goal_pose", PoseStamped)
    for t, typ in (("/goal_pose", PoseStamped), ("/manipulation/start", Bool),
                   ("/object_map_pose", PointStamped), ("/goal_reached", String)):
        r.listen(t, typ)
    c.start("object_approach_node.py", "/manipulation/goal_pose")


def send_object(c, mx, my, mz=0.5):
    t0 = time.time()
    c.rig.send("/manipulation/goal_pose", pose("base_link", *in_arm_frame(mx, my, mz)))
    return t0


def expected_goal(ox, oy):
    yaw = math.atan2(oy - CAMERA_Y, ox - CAMERA_X)
    return (ox - math.cos(yaw) * (APPROACH + CAMERA_X) + math.sin(yaw) * CAMERA_Y,
            oy - math.sin(yaw) * (APPROACH + CAMERA_X) - math.cos(yaw) * CAMERA_Y)


def case_approach_far(c):
    approach_rig(c)
    ox, oy = 2.18, 0.5  # 2.06 m from the camera
    t0 = send_object(c, ox, oy)
    spin(4.0, lambda: c.rig.since("/goal_pose", t0))
    spin(1.0)
    goals, starts = c.rig.since("/goal_pose", t0), c.rig.since("/manipulation/start", t0)
    seen = c.rig.since("/object_map_pose", t0)
    if not seen:
        raise SetupError("no /object_map_pose -- TF base_link -> map did not resolve")
    obj = seen[0].point
    if abs(obj.x - ox) > 0.01 or abs(obj.y - oy) > 0.01:
        return False, f"object landed at {xy(obj)} in map, sent ({ox}, {oy}) -- the TF bridge is off"
    if len(goals) != 1 or starts:
        return False, f"{len(goals)} /goal_pose, {len(starts)} /manipulation/start (want 1, 0)"
    g = goals[0]
    gx, gy = expected_goal(ox, oy)
    yaw = yaw_of(g.pose.orientation)
    cx = g.pose.position.x + math.cos(yaw) * CAMERA_X - math.sin(yaw) * CAMERA_Y
    cy = g.pose.position.y + math.sin(yaw) * CAMERA_X + math.cos(yaw) * CAMERA_Y
    dist = math.hypot(ox - cx, oy - cy)
    facing = ang(yaw, math.atan2(oy - cy, ox - cx))
    ok = (g.header.frame_id == "map" and abs(dist - APPROACH) < 0.02
          and math.hypot(gx - g.pose.position.x, gy - g.pose.position.y) < 0.02 and facing < 0.05)
    return ok, (f"goal {xy(g.pose.position)} in '{g.header.frame_id}', camera {dist:.3f} m from object, "
                f"facing error {math.degrees(facing):.1f} deg (want ({gx:.2f}, {gy:.2f}), camera 0.6 m)")


def case_approach_missing_camera(c):
    approach_rig(c, camera=False)
    t0 = send_object(c, 0.60, 0.10)
    c.rig.pub('/goal_reached', String)
    spin(3.0)
    c.rig.send('/goal_reached', String(data='success'))
    spin(0.5)
    goals = c.rig.since('/goal_pose', t0)
    starts = c.rig.since('/manipulation/start', t0)
    return not goals and not starts, f'missing camera TF: {len(goals)} goals, {len(starts)} starts (want 0/0)'


def case_approach_near(c):
    approach_rig(c)
    t0 = send_object(c, 0.60, 0.10)  # 0.43 m from the camera
    spin(3.0, lambda: c.rig.since("/manipulation/start", t0))
    spin(1.5)
    goals, starts = c.rig.since("/goal_pose", t0), c.rig.since("/manipulation/start", t0)
    ok = len(starts) == 1 and starts[0].data is True and not goals
    return ok, f"{len(starts)} /manipulation/start, {len(goals)} /goal_pose (want 1, 0)"


def case_approach_nav_succeeds(c):
    nav = c.nav2("succeed")
    approach_rig(c)
    c.start("goal_reached_publisher.py", "/goal_pose")
    t0 = send_object(c, 2.18, 0.5)
    spin(8.0, lambda: c.rig.since("/manipulation/start", t0))
    reached = [m.data for m in c.rig.since("/goal_reached", t0)]
    starts = c.rig.since("/manipulation/start", t0)
    ok = len(nav.goals) == 1 and reached == ["success"] and len(starts) == 1
    return ok, f"Nav2 got {len(nav.goals)} goal(s), /goal_reached {reached}, {len(starts)} /manipulation/start"


def case_approach_after_failure(c):
    nav = c.nav2("reject")
    approach_rig(c)
    c.start("goal_reached_publisher.py", "/goal_pose")
    send_object(c, 2.18, 0.5)
    if not spin(8.0, lambda: nav.goals):
        raise SetupError("the first approach goal never reached the mock Nav2")
    if not spin(5.0, lambda: c.rig.got["/goal_reached"]):
        return False, "Nav2 rejected goal 1; /goal_reached silent"
    t1 = send_object(c, 1.5, -1.0)  # a second, different object, inside the back-off
    spin(1.0)
    early = len(c.rig.since("/goal_pose", t1))
    spin(RETRY_BACKOFF)
    t2 = send_object(c, 1.5, -1.0)  # the same object again, after the back-off
    spin(5.0, lambda: c.rig.since("/goal_pose", t2))
    second = c.rig.since("/goal_pose", t2)
    reached = [m.data for _, m in c.rig.got["/goal_reached"]]
    return bool(second) and not early, (f"Nav2 rejected goal 1; /goal_reached {reached}; second object -> "
                                        f"{early} /goal_pose inside the back-off (want 0), {len(second)} after it")


def case_approach_after_release(c):
    """A finished cycle must not block the next one. An in-range object starts the arm
    and sets the guard with no nav goal, so no /goal_reached will ever clear it."""
    approach_rig(c)
    c.rig.pub("/manipulator/release", Bool)
    t0 = send_object(c, 0.60, 0.10)  # in range: /manipulation/start, no goal
    if not spin(4.0, lambda: c.rig.since("/manipulation/start", t0)):
        raise SetupError("the in-range object never produced /manipulation/start")
    c.rig.send("/manipulator/release", Bool(data=True))
    spin(1.0)
    t1 = send_object(c, 2.18, 0.5)  # a second object, out of range
    spin(5.0, lambda: c.rig.since("/goal_pose", t1))
    second = c.rig.since("/goal_pose", t1)
    return bool(second), f"cycle 1 started the arm, then release; second object -> {len(second)} /goal_pose"


def bridge_rig(c):
    c.rig.pub("/goal_pose", PoseStamped)
    c.rig.listen("/goal_reached", String)
    c.start("goal_reached_publisher.py", "/goal_pose")


def case_bridge_aborts(c):
    nav = c.nav2("abort")
    bridge_rig(c)
    t0 = time.time()
    c.rig.send("/goal_pose", pose("map", 1.0, 0.0))
    spin(5.0, lambda: c.rig.since("/goal_reached", t0))
    reached = [m.data for m in c.rig.since("/goal_reached", t0)]
    return len(nav.goals) == 1 and reached == ["failed"], f"Nav2 got {len(nav.goals)} goal(s); /goal_reached {reached}"


def case_bridge_server_down(c):
    bridge_rig(c)
    t0 = time.time()
    c.rig.send("/goal_pose", pose("map", 1.0, 0.0))
    spin(8.0, lambda: c.rig.since("/goal_reached", t0))
    got = [(round(ts - t0, 1), m.data) for ts, m in c.rig.got["/goal_reached"] if ts >= t0]
    ok = any(m == "failed" and dt <= 6.0 for dt, m in got)
    return ok, f"no Nav2 on the channel; /goal_reached in 8 s: {got or 'nothing'}"


def case_bridge_nav2_goes_away(c):
    nav = c.nav2("hang")
    bridge_rig(c)
    c.rig.send("/goal_pose", pose("map", 1.0, 0.0))
    if not spin(8.0, lambda: nav.goals):
        raise SetupError("the goal never reached the mock Nav2")
    spin(1.5)  # accepted, navigating
    before = [m.data for _, m in c.rig.got["/goal_reached"]]
    t0 = time.time()
    nav.close()  # Nav2 dies with the goal still open
    spin(10.0, lambda: c.rig.since("/goal_reached", t0))
    after = [m.data for m in c.rig.since("/goal_reached", t0)]
    return not before and after == ["failed"], (f"goal accepted, /goal_reached {before or 'silent'}; "
                                                f"Nav2 gone -> {after or 'nothing in 10 s'}")


def glasses_rig(c, camera=True):
    r = c.rig
    if camera:
        r.static.sendTransform([tf('robot_base_link', CAMERA_FRAME, CAMERA_X, CAMERA_Y, 0.5425, 0)])
    for t, typ in (("/aria/fused_pose", PoseStamped), ("/goto_glasses/trigger", Empty),
                   ("/manipulator/return_to_user", Bool)):
        r.pub(t, typ)
    r.listen("/return_to_user/goal_reached", String)
    c.start("goto_glasses.py", "/goto_glasses/trigger")


def outbound(c, nav, fused):
    for _ in range(3):
        c.rig.send("/aria/fused_pose", fused)
        spin(0.2)
    c.rig.send("/goto_glasses/trigger", Empty())
    if not spin(8.0, lambda: nav.goals):
        raise SetupError("the outbound goal never reached the mock Nav2")
    spin(1.5)  # result delivered, outbound flag cleared
    return nav.goals[0][1]


def case_return_retry(c):
    nav = c.nav2("succeed")
    glasses_rig(c)
    outbound(c, nav, pose("map", 1.0, 1.0))
    nav.close()
    spin(2.5)  # graph forgets the server
    c.rig.send("/manipulator/return_to_user", Bool(data=True))
    spin(7.0)  # goto_glasses waits 5 s for a server, then gives up
    nav2 = c.nav2("succeed")
    spin(1.5)
    t1 = time.time()
    c.rig.send("/manipulator/return_to_user", Bool(data=True))
    spin(8.0, lambda: nav2.goals)
    res = [m.data for m in c.rig.since("/return_to_user/goal_reached", 0)]
    return bool(nav2.goals), (f"return 1 with Nav2 down; return 2 with Nav2 back -> "
                              f"{len(nav2.goals)} goal(s); /return_to_user/goal_reached {res or 'silent'}")


def case_return_camera(c):
    nav = c.nav2('succeed')
    glasses_rig(c)
    ux, uy, user_yaw = 1.0, 2.0, 0.7
    outbound(c, nav, pose('map', ux, uy, yaw=user_yaw))
    c.rig.send('/manipulator/return_to_user', Bool(data=True))
    if not spin(6.0, lambda: len(nav.goals) == 2):
        return False, 'return goal missing'
    goal = nav.goals[-1][1]
    yaw = yaw_of(goal.pose.orientation)
    cx = goal.pose.position.x + math.cos(yaw) * CAMERA_X - math.sin(yaw) * CAMERA_Y
    cy = goal.pose.position.y + math.sin(yaw) * CAMERA_X + math.cos(yaw) * CAMERA_Y
    distance = math.hypot(ux - cx, uy - cy)
    ok = abs(distance - 0.5) < 0.01 and ang(yaw, math.atan2(uy-cy, ux-cx)) < 0.01
    return ok, f'return camera clearance {distance:.3f} m (want 0.5 m), including lateral TF offset'


def case_return_missing_camera(c):
    nav = c.nav2('succeed')
    glasses_rig(c, camera=False)
    outbound(c, nav, pose('map', 1, 1))
    c.rig.send('/manipulator/return_to_user', Bool(data=True))
    spin(3.0)
    if len(nav.goals) != 1:
        return False, f'missing camera TF: {len(nav.goals)-1} return goals (want 0)'
    c.rig.static.sendTransform([tf('robot_base_link', CAMERA_FRAME, CAMERA_X, CAMERA_Y, 0.5425, 0)])
    spin(1.0)
    c.rig.send('/manipulator/return_to_user', Bool(data=True))
    recovered = spin(6.0, lambda: len(nav.goals) == 2)
    return recovered, f'no return without camera TF; retry after TF appears: {len(nav.goals)-1} goal (want 1)'


def case_fused_pose_frame(c):
    # robot at (3, 1) in map facing +y; the wearer 1 m in front of it, facing the same way
    c.rig.static.sendTransform([tf("map", "robot_base_link", 3.0, 1.0, 0.0, math.pi / 2)])
    nav = c.nav2("succeed")
    glasses_rig(c)
    g = outbound(c, nav, pose("robot_base_link", 1.0, 0.0, 0.0, 0.0))  # as pose_fusion_node stamps it
    ux, uy, uyaw = 3.0, 2.0, math.pi / 2  # the same wearer, in map
    want = (ux - math.sin(uyaw) * SIDE_OFFSET, uy + math.cos(uyaw) * SIDE_OFFSET)
    p = g.pose.position
    ok = g.header.frame_id == "map" and math.hypot(p.x - want[0], p.y - want[1]) < 0.05
    return ok, (f"goal {xy(p)} in '{g.header.frame_id}'; the wearer in map puts it at "
                f"({want[0]:.2f}, {want[1]:.2f}); read raw it would be (1.00, 0.60)")


def cloud(points=20000):
    """A MID360-sized frame [inferred: ~200k points/s at 10 Hz], Livox PointXYZRTLT layout."""
    m = PointCloud2()
    m.header.frame_id = "livox_frame"
    f32, u8, f64 = PointField.FLOAT32, PointField.UINT8, PointField.FLOAT64
    m.fields = [PointField(name=n, offset=o, datatype=d, count=1) for n, o, d in
                (("x", 0, f32), ("y", 4, f32), ("z", 8, f32), ("intensity", 12, f32),
                 ("tag", 16, u8), ("line", 17, u8), ("timestamp", 18, f64))]
    m.height, m.width, m.point_step = 1, points, 26
    m.row_step = m.point_step * points
    m.is_dense = True
    m.data = bytes(m.row_step)
    return m


def case_qos_relay(c):
    r = c.rig
    r.pub("/livox/lidar", PointCloud2)  # depth 10 = RELIABLE, as the Livox driver publishes
    r.listen("/cloud_relay", PointCloud2, QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT))
    c.start("qos_relay.py", "/livox/lidar")
    info = r.get_publishers_info_by_topic("/cloud_relay")
    rel = [i.qos_profile.reliability for i in info]
    msg, n, t0 = cloud(), 50, time.time()
    for _ in range(n):
        msg.header.stamp = r.get_clock().now().to_msg()
        r.send("/livox/lidar", msg)
        spin(0.1)
    spin(1.5)
    got = r.since("/cloud_relay", t0)
    lat = [ts - (m.header.stamp.sec + m.header.stamp.nanosec * 1e-9) for ts, m in r.got["/cloud_relay"] if ts >= t0]
    best_effort = bool(rel) and all(x == ReliabilityPolicy.BEST_EFFORT for x in rel)
    ok = best_effort and len(got) >= 0.9 * n
    return ok, (f"/cloud_relay {'BEST_EFFORT' if best_effort else rel}; {len(got)}/{n} frames of "
                f"{msg.row_step // 1000} kB at 10 Hz" + (f"; mean latency {1000 * sum(lat) / len(lat):.1f} ms" if lat else ""))


def case_robot_pose(c):
    x, y, yaw = 2.0, -1.0, 0.5
    c.rig.static.sendTransform([tf("map", "robot_base_link", x, y, 0.0, yaw)])
    c.rig.listen("/robot_pose", PoseStamped)
    c.start("pose_publisher.py", "/robot_pose", kind="pub")
    spin(1.0)
    t0 = time.time()
    spin(3.0)
    got = c.rig.since("/robot_pose", t0)
    if not got:
        return False, "no /robot_pose in 3 s"
    hz, m = len(got) / 3.0, got[-1]
    ok = (8.0 <= hz <= 12.0 and m.header.frame_id == "map"
          and math.hypot(m.pose.position.x - x, m.pose.position.y - y) < 0.01 and ang(yaw_of(m.pose.orientation), yaw) < 0.01)
    return ok, f"{hz:.1f} Hz, '{m.header.frame_id}', at {xy(m.pose.position)} yaw {yaw_of(m.pose.orientation):.2f} (want ({x}, {y}) yaw {yaw})"


# each node, and the topic that shows it is up (as the cases above start them)
READY = [("object_approach_node.py", "/manipulation/goal_pose", "sub"),
         ("goal_reached_publisher.py", "/goal_pose", "sub"),
         ("goto_glasses.py", "/goto_glasses/trigger", "sub"),
         ("qos_relay.py", "/livox/lidar", "sub"),
         ("pose_publisher.py", "/robot_pose", "pub")]


def case_clean_ctrl_c(c):
    """Ctrl+C (SIGINT, as Case.close sends it) must end each node with exit code 0 and
    no traceback. Before the F4 fix all five printed one, in three shapes."""
    bad = []
    for script, topic, kind in READY:
        out = LOG.parent / f"bench_nav_ctrl_c_{script}.txt"
        with open(out, "w") as f:
            p = c.start(script, topic, kind=kind, out=f)
            os.killpg(p.pid, signal.SIGINT)
            try:
                code = p.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                code = f"hung, killed ({p.wait(5)})"
        text = out.read_text(errors="replace")
        c.log.write(f"\n===== {script} after SIGINT, exit {code} =====\n{text}")
        if code != 0 or "Traceback" in text:
            bad.append(f"{script} exit {code}{', traceback' if 'Traceback' in text else ''}")
    return not bad, "; ".join(bad) or "all five exited 0 with no traceback"


CASES = [  # name, kind, audit id, scripts it starts, function
    ("approach, far object", "control", "", ["object_approach_node.py"], case_approach_far),
    ("approach, near object", "control", "", ["object_approach_node.py"], case_approach_near),
    ("approach, missing camera", "control", "", ["object_approach_node.py"], case_approach_missing_camera),
    ("approach, nav succeeds", "control", "", ["object_approach_node.py", "goal_reached_publisher.py"], case_approach_nav_succeeds),
    ("approach after nav failure", "xfail", "F1", ["object_approach_node.py", "goal_reached_publisher.py"], case_approach_after_failure),
    ("approach after release", "xfail", "F5", ["object_approach_node.py"], case_approach_after_release),
    ("goal bridge, nav aborts", "control", "", ["goal_reached_publisher.py"], case_bridge_aborts),
    ("goal bridge, server down", "xfail", "F1", ["goal_reached_publisher.py"], case_bridge_server_down),
    ("goal bridge, Nav2 goes away", "xfail", "F1", ["goal_reached_publisher.py"], case_bridge_nav2_goes_away),
    ("return retry", "xfail", "F2", ["goto_glasses.py"], case_return_retry),
    ("return camera clearance", "control", "", ["goto_glasses.py"], case_return_camera),
    ("return missing camera", "control", "", ["goto_glasses.py"], case_return_missing_camera),
    ("fused pose frame", "xfail", "E1", ["goto_glasses.py"], case_fused_pose_frame),
    ("QoS relay", "control", "J4", ["qos_relay.py"], case_qos_relay),
    ("robot pose", "control", "", ["pose_publisher.py"], case_robot_pose),
    ("clean Ctrl+C", "xfail", "F4", [s for s, _, _ in READY], case_clean_ctrl_c),
]


def missing(scripts):
    return sorted({m for s in scripts for m in NEEDS[s] if importlib.util.find_spec(m) is None})


def main():
    global EX
    only = sys.argv[1:]  # optional case-name substrings
    rclpy.init()
    EX = SingleThreadedExecutor()
    results = []  # (name, audit, tag, detail)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w") as log:
        for i, (name, kind, audit, scripts, fn) in enumerate(CASES):
            if only and not any(o in name for o in only):
                continue
            lack = missing(scripts)
            if lack:
                results.append((name, audit, "SKIP ", f"{sys.executable} lacks {', '.join(lack)}"))
                continue
            print(f"  ... {name}", flush=True)
            log.write(f"\n########## {name} ##########\n")
            c = Case(f"c{i}", log)
            try:
                ok, detail = fn(c)
                tag = ("PASS " if ok else "FAIL ") if kind == "control" else ("XPASS" if ok else "XFAIL")
            except SetupError as e:
                tag, detail = "FAIL ", f"setup: {e}"
            finally:
                c.close()
            results.append((name, audit, tag, detail))
    EX.shutdown()
    rclpy.shutdown()

    print()
    for name, audit, tag, detail in results:
        print(f"  [{tag}] {name + (f' ({audit})' if audit else ''):34s} {detail}")
    tags = [t for _, _, t, _ in results]
    if "XPASS" in tags:
        print("\n  XPASS: an expected failure did not reproduce -- retag the finding (CODE_AUDIT / TESTBENCH_PLAN W7).")
    if tags and all(t == "SKIP " for t in tags):
        print("\nRESULT: SKIPPED -- no case could run here (never a pass)")
        return 3
    failed = "FAIL " in tags
    print("\nRESULT:", "FAIL (a control or a case's setup failed)" if failed
          else "PASS (controls pass; XFAIL = known finding reproduced; SKIPs listed above)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
