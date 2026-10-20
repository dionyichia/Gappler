#!/usr/bin/env python3
"""FAST-LIVO2 pose to odom -> robot_base_link (option 2: SLAM Toolbox keeps map -> odom and /map).

The transform, written down
---------------------------
The mapper (U-AMC/FAST-LIVO2-ROS2 at a09599a) publishes /aft_mapped_to_init: the pose P(t) of its IMU body
(child aft_mapped) in its world frame camera_init. Three facts fix the bridge:

1. The body is not the robot_base_link. The body origin sits at BODY_IN_BASE in robot_base_link, with identity
   rotation: the lidar_mount (0.18, 0, 0.2) minus the mapper's LiDAR->IMU extrinsic_T (-0.011, -0.02329, 0.04412),
   i.e. (0.191, 0.02329, 0.15588) m. This is the corrected sign (T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md).
2. odom is defined as robot_base_link at startup: T_odom_base(first sample) is the identity, position, heading
   and tilt. camera_init is only roughly gravity-aligned (the first pose in the T3.5d bags carries about 0.7 degrees
   of roll), and the robot starts on a level floor, so taking the startup pose as the origin removes that tilt
   and keeps a level drive level.
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

# Body (IMU) origin in robot_base_link, identity rotation. Derivation in the docstring above.
BODY_IN_BASE = (0.191, 0.02329, 0.15588)
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


class OdomFromMapper:
    """Maps each mapper pose to the base pose in an odom frame that equals robot_base_link at startup."""

    def __init__(self, body_in_base=BODY_IN_BASE):
        self.o = tuple(body_in_base)
        self._r0 = None
        self._p0 = None

    def update(self, position, quaternion):
        """position (x, y, z) and quaternion (x, y, z, w) of aft_mapped in camera_init -> same for the base in odom."""
        if not all(math.isfinite(c) for c in tuple(position) + tuple(quaternion)):
            raise ValueError("non-finite pose")
        r = quat_to_mat(quaternion)
        if self._r0 is None:
            self._r0, self._p0 = _transpose(r), list(position)  # store R0^T and p0
        r_rel = _mul(self._r0, r)
        p_rel = _vec(self._r0, [position[i] - self._p0[i] for i in range(3)])
        ro = _vec(r_rel, self.o)
        pos = tuple(self.o[i] + p_rel[i] - ro[i] for i in range(3))
        return pos, mat_to_quat(r_rel)

    def reset(self):
        """Make the next sample the new startup (a mapper restart or a stale gap)."""
        self._r0 = self._p0 = None
