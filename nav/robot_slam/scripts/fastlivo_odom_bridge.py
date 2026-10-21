#!/usr/bin/env python3
"""FAST-LIVO2 pose to odom -> robot_base_link (option 2: SLAM Toolbox keeps map -> odom and /map).

The transform, written down
---------------------------
The mapper (U-AMC/FAST-LIVO2-ROS2 at a09599a) publishes /aft_mapped_to_init: the pose P(t) of its IMU body
(child aft_mapped) in its world frame camera_init. Three facts fix the bridge:

1. The body is not the robot_base_link. The body origin sits at body_in_base_m (config/fastlivo_bridge.yaml) in
   robot_base_link, with identity rotation: the lidar_mount (0.18, 0, 0.2) minus the mapper's LiDAR->IMU extrinsic_T
   (-0.011, -0.02329, 0.04412), i.e. (0.191, 0.02329, 0.15588) m. This is the corrected sign
   (T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md).
2. odom is defined as robot_base_link at startup: T_odom_base(first sample) is the identity, position, heading
   and tilt. camera_init is aligned to the accelerometer's idea of up and is off-level by about the first pose's tilt
   (T3.5d: 0.73 deg of roll, matched by the measured floor tilt, see the T3.5e write-up), and the robot starts on a
   level floor, so taking the full startup pose as the origin removes that tilt and keeps a level drive level. A
   first pose tilted more than max_startup_tilt_deg is refused: the robot was not level or the alignment failed.
3. Per sample, with P0 the first pose and Tb the body in the base (rotation identity):

       T_odom_base(t) = Tb * P0^-1 * P(t) * Tb^-1

   For Tb with identity rotation this is, with R_rel = R0^T R(t) and p_rel = R0^T (p(t) - p0):
       rotation of the base = R_rel
       position of the base = o + p_rel - R_rel * o          (o = BODY_IN_BASE)
   so a turn in place about the base centre leaves the base where it was, and a straight drive moves it along
   its own forward.

Everything here is stdlib so the L0 bench can test it without ROS (bench/test_fastlivo_odom_bridge.py).
"""
import math

MAPPER_FRAME = "camera_init"
MAPPER_CHILD = "aft_mapped"


def check_frames(frame_id: str, child_frame_id: str) -> None:
    """Refuse loudly unless the odometry is the mapper's own camera_init -> aft_mapped."""
    if frame_id != MAPPER_FRAME or child_frame_id != MAPPER_CHILD:
        raise ValueError(
            f"expected {MAPPER_FRAME} -> {MAPPER_CHILD}, got {frame_id!r} -> {child_frame_id!r}")


def quat_to_mat(q):
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n == 0 or not math.isfinite(n):
        raise ValueError("quaternion is zero or not finite")
    x, y, z, w = x / n, y / n, z / n, w / n
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def mat_to_quat(r):
    """Rotation matrix to (x, y, z, w) with w >= 0."""
    t = r[0][0] + r[1][1] + r[2][2]
    if t > 0:
        s = math.sqrt(t + 1) * 2
        q = ((r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s, (r[1][0] - r[0][1]) / s, s / 4)
    else:
        i = max(range(3), key=lambda k: r[k][k])
        j, k = (i + 1) % 3, (i + 2) % 3
        s = math.sqrt(r[i][i] - r[j][j] - r[k][k] + 1) * 2
        v = [0.0] * 4
        v[i] = s / 4
        v[j] = (r[j][i] + r[i][j]) / s
        v[k] = (r[k][i] + r[i][k]) / s
        v[3] = (r[k][j] - r[j][k]) / s
        q = tuple(v)
    return q if q[3] >= 0 else tuple(-c for c in q)


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _vec(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def _transpose(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


class StartupTiltError(ValueError):
    """The first mapper pose is tilted too far for 'the robot started level' to hold."""


class MapperJumpError(ValueError):
    """Consecutive mapper poses are too far apart: the mapper restarted or lost its origin."""


def shift_stamp(sec, nanosec, offset_s):
    """A message stamp moved by offset_s seconds, in exact integer nanoseconds. T3.5f measured the mapper's pose stamps about
    0.15 s later than the pose they carry (time_offset_sweep.py, three recordings), so stamp_offset_s: -0.15 restamps them."""
    return divmod(sec * 1_000_000_000 + nanosec + round(offset_s * 1e9), 1_000_000_000)


class ScanPairSelector:
    """Keep only the final pose of each scan.

    In visual mode the mapper publishes twice per scan: after the partial LIO update at the image time (before the visual
    correction) and after the final one. A message arriving within window_s of the previous one is a later pose of the same
    scan and goes out at once. A message with no earlier one in the window is held, and goes out only if no later one arrives
    (a scan with a single pose) once window_s has passed. Arrival time, not message stamp, because the stamps' meaning changes
    if the mapper is patched to stamp measurement time. Measured on handdriven1: gaps within a scan 0 to 50 ms, between scans
    55 to 100 ms, so 0.05 s separates them except in a few percent of scans (three poses in a window publish the later two).
    Use select_final_pose: false for a LiDAR-only mapper config (one pose per scan), where nothing needs holding."""

    def __init__(self, window_s):
        self.window_s = window_s
        self._last = None
        self._held = None

    def offer(self, now, item):
        """A pose arrived. Returns the poses to publish now."""
        if self._last is not None and now - self._last <= self.window_s:
            self._held = None  # the held one was the partial pose of this scan
            self._last = now
            return [item]
        out = [self._held] if self._held is not None else []
        self._held, self._last = item, now
        return out

    def poll(self, now):
        """Call regularly. Returns a held single pose once the window has passed with no partner."""
        if self._held is not None and now - self._last > self.window_s:
            item, self._held = self._held, None
            return [item]
        return []


class FreshnessGate:
    """True while the newest mapper pose is younger than window_s. Nothing received yet is stale."""

    def __init__(self, window_s):
        self.window_s = window_s
        self._last = None

    def received(self, now):
        self._last = now

    def fresh(self, now):
        return self._last is not None and now - self._last <= self.window_s


def roll_pitch(r):
    """Roll and pitch (rad) of a rotation matrix, ZYX convention."""
    return math.atan2(r[2][1], r[2][2]), math.asin(max(-1.0, min(1.0, -r[2][0])))


def twist_between(a, b, dt):
    """Linear and angular velocity of pose b relative to pose a, both (rotation, position) in odom, in a's frame.

    Exact rotation vector (log map), so a turn of any size over dt gives the right rate."""
    ra, pa = a
    rb, pb = b
    rel = _mul(_transpose(ra), rb)
    v = _vec(_transpose(ra), [pb[i] - pa[i] for i in range(3)])
    s = [(rel[2][1] - rel[1][2]) / 2, (rel[0][2] - rel[2][0]) / 2, (rel[1][0] - rel[0][1]) / 2]
    sn = math.sqrt(sum(c * c for c in s))
    angle = math.atan2(sn, (rel[0][0] + rel[1][1] + rel[2][2] - 1) / 2)
    w = [0.0, 0.0, 0.0] if sn < 1e-15 else [c * angle / sn for c in s]
    return [c / dt for c in v], [c / dt for c in w]


class OdomFromMapper:
    """Maps each mapper pose to the base pose in an odom frame that equals robot_base_link at startup.

    max_startup_tilt_deg: refuse a first pose tilted more than this (None = no check).
    max_jump_m: refuse a step between consecutive poses larger than this (None = no check)."""

    def __init__(self, body_in_base, max_startup_tilt_deg=None, max_jump_m=None):
        self.o = tuple(float(c) for c in body_in_base)
        if len(self.o) != 3:
            raise ValueError("body_in_base must be three numbers (x, y, z) in metres")
        self.max_tilt = None if max_startup_tilt_deg is None else math.radians(max_startup_tilt_deg)
        self.max_jump = max_jump_m
        self._r0 = None
        self._p0 = None
        self._last = None

    def update(self, position, quaternion):
        """position (x, y, z) and quaternion (x, y, z, w) of aft_mapped in camera_init -> same for the base in odom."""
        if not all(math.isfinite(c) for c in tuple(position) + tuple(quaternion)):
            raise ValueError("non-finite pose")
        r = quat_to_mat(quaternion)
        if self._r0 is None:
            if self.max_tilt is not None:
                roll, pitch = roll_pitch(r)
                if max(abs(roll), abs(pitch)) > self.max_tilt:
                    raise StartupTiltError("startup roll %.2f deg, pitch %.2f deg: the robot was not level or the mapper's gravity "
                                           "alignment failed (limit %.1f deg)" % (math.degrees(roll), math.degrees(pitch), math.degrees(self.max_tilt)))
            self._r0, self._p0 = _transpose(r), list(position)  # store R0^T and p0
        elif self.max_jump is not None and math.dist(position, self._last) > self.max_jump:
            raise MapperJumpError("mapper pose stepped %.2f m between samples (limit %.2f m): mapper restart?" % (math.dist(position, self._last), self.max_jump))
        self._last = list(position)
        r_rel = _mul(self._r0, r)
        p_rel = _vec(self._r0, [position[i] - self._p0[i] for i in range(3)])
        ro = _vec(r_rel, self.o)
        pos = tuple(self.o[i] + p_rel[i] - ro[i] for i in range(3))
        return pos, mat_to_quat(r_rel)

    def reset(self):
        """Make the next sample the new startup (an operator-accepted mapper restart)."""
        self._r0 = self._p0 = self._last = None


def main():
    """ROS node. Imports stay inside so the L0 tests need no ROS."""
    import rclpy
    from geometry_msgs.msg import TransformStamped
    from nav_msgs.msg import Odometry
    from rclpy.executors import ExternalShutdownException
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from tf2_ros import TransformBroadcaster

    class FastlivoOdomBridge(Node):
        def __init__(self):
            super().__init__("fastlivo_odom_bridge")
            self.declare_parameter("body_in_base_m", Parameter.Type.DOUBLE_ARRAY)  # no default: the config file must supply it
            self.declare_parameter("mapper_topic", "/aft_mapped_to_init")
            self.declare_parameter("odom_frame", "odom")
            self.declare_parameter("base_frame", "robot_base_link")
            self.declare_parameter("freshness_window_s", 0.5)
            self.declare_parameter("max_startup_tilt_deg", 2.0)
            self.declare_parameter("max_jump_m", 0.5)
            self.declare_parameter("publish_odom", False)
            self.declare_parameter("odom_topic", "/odom")
            self.declare_parameter("select_final_pose", True)
            self.declare_parameter("pair_window_s", 0.05)
            self.declare_parameter("stamp_offset_s", 0.0)
            p = lambda name: self.get_parameter(name).value
            self._odom_frame, self._base_frame = p("odom_frame"), p("base_frame")
            self._core = OdomFromMapper(p("body_in_base_m"), p("max_startup_tilt_deg"), p("max_jump_m"))
            self._gate = FreshnessGate(p("freshness_window_s"))
            self._stamp_offset = p("stamp_offset_s")
            self._tf = TransformBroadcaster(self)
            self._odom_pub = self.create_publisher(Odometry, p("odom_topic"), 10) if p("publish_odom") else None
            self._stale_reported = False
            self._failed = False
            self._prev = None  # (rotation, position, stamp seconds) of the previous base pose, for the optional twist
            self._select = ScanPairSelector(p("pair_window_s")) if p("select_final_pose") else None
            self.create_subscription(Odometry, p("mapper_topic"), self._on_pose, 10)
            self.create_timer(0.1, self._watch)
            if self._select is not None:
                self.create_timer(0.01, self._flush_single)
            self.get_logger().info("odom -> %s from %s, body offset %s m, stops after %.2f s of silence"
                                   % (self._base_frame, p("mapper_topic"), tuple(p("body_in_base_m")), p("freshness_window_s")))

        def _now(self):
            return self.get_clock().now().nanoseconds * 1e-9

        def _on_pose(self, msg):
            if self._failed:
                return
            try:
                check_frames(msg.header.frame_id, msg.child_frame_id)
                pos, quat = self._core.update(
                    (msg.pose.pose.position.x, msg.pose.pose.position.y, msg.pose.pose.position.z),
                    (msg.pose.pose.orientation.x, msg.pose.pose.orientation.y, msg.pose.pose.orientation.z, msg.pose.pose.orientation.w))
            except (ValueError, StartupTiltError, MapperJumpError) as err:
                self._failed = True  # fail loud and stay silent: a wrong odom edge is worse than none
                self.get_logger().error("refusing mapper pose, publishing nothing until the bridge is restarted: %s" % err)
                return
            self._gate.received(self._now())
            if self._stale_reported:
                self.get_logger().info("mapper output is back")
                self._stale_reported = False
            item = (msg, pos, quat)
            for ready in (self._select.offer(self._now(), item) if self._select is not None else [item]):
                self._publish(*ready)

        def _flush_single(self):
            for ready in self._select.poll(self._now()):
                self._publish(*ready)

        def _publish(self, msg, pos, quat):
            t = TransformStamped()
            t.header.stamp.sec, t.header.stamp.nanosec = shift_stamp(msg.header.stamp.sec, msg.header.stamp.nanosec, self._stamp_offset)
            t.header.frame_id, t.child_frame_id = self._odom_frame, self._base_frame
            t.transform.translation.x, t.transform.translation.y, t.transform.translation.z = pos
            t.transform.rotation.x, t.transform.rotation.y, t.transform.rotation.z, t.transform.rotation.w = quat
            self._tf.sendTransform(t)
            if self._odom_pub is not None:
                self._publish_odom(msg, pos, quat)

        def _publish_odom(self, msg, pos, quat):
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            rot = quat_to_mat(quat)
            o = Odometry()
            o.header.stamp.sec, o.header.stamp.nanosec = shift_stamp(msg.header.stamp.sec, msg.header.stamp.nanosec, self._stamp_offset)
            o.header.frame_id, o.child_frame_id = self._odom_frame, self._base_frame
            o.pose.pose.position.x, o.pose.pose.position.y, o.pose.pose.position.z = pos
            o.pose.pose.orientation.x, o.pose.pose.orientation.y, o.pose.pose.orientation.z, o.pose.pose.orientation.w = quat
            if self._prev is not None and stamp > self._prev[2]:
                v, w = twist_between((self._prev[0], self._prev[1]), (rot, list(pos)), stamp - self._prev[2])
                o.twist.twist.linear.x, o.twist.twist.linear.y, o.twist.twist.linear.z = v
                o.twist.twist.angular.x, o.twist.twist.angular.y, o.twist.twist.angular.z = w
            self._prev = (rot, list(pos), stamp)
            self._odom_pub.publish(o)

        def _watch(self):
            if not self._failed and self._gate._last is not None and not self._gate.fresh(self._now()) and not self._stale_reported:
                self._stale_reported = True
                self.get_logger().warning("no mapper pose for %.2f s: publishing nothing on odom -> %s until it returns"
                                          % (self._gate.window_s, self._base_frame))

    rclpy.init()
    node = FastlivoOdomBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
