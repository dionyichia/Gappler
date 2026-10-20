"""The FAST-LIVO2 to odom -> robot_base_link transform, checked with plain trigonometry (stdlib, no ROS).

The mapper reports the IMU body pose in camera_init. The bridge must turn that into the robot_base_link
pose in an odom frame that equals robot_base_link at startup, whatever tilt camera_init has.
"""
import importlib.util
import math
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fastlivo_odom_bridge", REPO / "nav/robot_slam/scripts/fastlivo_odom_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

OFFSET = bridge.BODY_IN_BASE  # IMU body origin in robot_base_link, identity rotation


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def tr(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def quat(r):
    """Rotation matrix to (x, y, z, w), well-conditioned branch."""
    t = r[0][0] + r[1][1] + r[2][2]
    if t > 0:
        s = math.sqrt(t + 1) * 2
        return ((r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s, (r[1][0] - r[0][1]) / s, s / 4)
    i = max(range(3), key=lambda k: r[k][k])
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(r[i][i] - r[j][j] - r[k][k] + 1) * 2
    q = [0.0] * 4
    q[i] = s / 4
    q[j] = (r[j][i] + r[i][j]) / s
    q[k] = (r[k][i] + r[i][k]) / s
    q[3] = (r[k][j] - r[j][k]) / s
    return tuple(q)


def body_pose(base_rot, base_pos, tilt=None):
    """The mapper's pose of the body in camera_init for a base pose in a gravity-levelled world.

    camera_init is the world rotated by `tilt` (None = not tilted)."""
    body_pos = [base_pos[i] + mv(base_rot, OFFSET)[i] for i in range(3)]
    rot, pos = base_rot, body_pos
    if tilt is not None:
        rot, pos = mm(tr(tilt), rot), mv(tr(tilt), pos)
    return pos, quat(rot)


def yaw_pitch_roll(q):
    x, y, z, w = q
    return (math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)),
            math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x)))),
            math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))


class BridgeTransformTests(unittest.TestCase):
    def test_body_offset_is_lidar_mount_minus_extrinsic(self):
        lidar_mount = (0.18, 0.0, 0.2)  # shared/global_config.yaml geometry.lidar_mount
        extrinsic_t = (-0.011, -0.02329, 0.04412)  # corrected Mid-360 extrinsic_T, identity rotation
        derived = tuple(m - t for m, t in zip(lidar_mount, extrinsic_t))
        for got, want in zip(OFFSET, derived):
            self.assertAlmostEqual(got, want, places=9)
        for got, rounded in zip(OFFSET, (0.191, 0.023, 0.156)):
            self.assertAlmostEqual(got, rounded, delta=1e-3)

    def test_first_sample_is_the_identity(self):
        odom = bridge.OdomFromMapper()
        pos, q = odom.update(*body_pose(mm(rz(0.5), mm(ry(0.02), rx(-0.01))), (3.0, -2.0, 0.4)))
        for v in pos:
            self.assertAlmostEqual(v, 0.0, places=9)
        self.assertAlmostEqual(abs(q[3]), 1.0, places=9)

    def test_straight_drive_moves_the_base_along_its_own_forward(self):
        odom = bridge.OdomFromMapper()
        start_yaw = math.radians(30)  # robot starts facing 30 degrees in camera_init
        odom.update(*body_pose(rz(start_yaw), (1.0, 2.0, 0.0)))
        d = 0.8
        pos, q = odom.update(*body_pose(rz(start_yaw), (1.0 + d * math.cos(start_yaw), 2.0 + d * math.sin(start_yaw), 0.0)))
        self.assertAlmostEqual(pos[0], d, places=9)
        self.assertAlmostEqual(pos[1], 0.0, places=9)
        self.assertAlmostEqual(yaw_pitch_roll(q)[0], 0.0, places=9)

    def test_turning_in_place_about_the_base_centre_does_not_move_the_base(self):
        odom = bridge.OdomFromMapper()
        odom.update(*body_pose(rz(0.0), (0.0, 0.0, 0.0)))
        for deg in (10, 90, 179, -120, 360):
            pos, q = odom.update(*body_pose(rz(math.radians(deg)), (0.0, 0.0, 0.0)))
            for v in pos:
                self.assertAlmostEqual(v, 0.0, places=9, msg="%d deg" % deg)
            want = math.atan2(math.sin(math.radians(deg)), math.cos(math.radians(deg)))
            self.assertAlmostEqual(yaw_pitch_roll(q)[0], want, places=9)

    def test_startup_tilt_of_camera_init_cancels_and_a_level_drive_stays_level(self):
        tilt = mm(ry(math.radians(-0.4)), rx(math.radians(0.73)))  # the 0.7 degree start tilt seen in the T3.5d bags
        odom = bridge.OdomFromMapper()
        radius, start = 1.5, math.radians(20)
        odom.update(*body_pose(rz(start + math.pi / 2), (radius * math.cos(start), radius * math.sin(start), 0.0), tilt))
        for step in range(1, 40):
            a = start + step * math.radians(9)
            pos, q = odom.update(*body_pose(rz(a + math.pi / 2), (radius * math.cos(a), radius * math.sin(a), 0.0), tilt))
            self.assertAlmostEqual(pos[2], 0.0, places=9, msg="z drifted on a level drive")
            yaw, pitch, roll = yaw_pitch_roll(q)
            self.assertAlmostEqual(pitch, 0.0, places=9)
            self.assertAlmostEqual(roll, 0.0, places=9)
            # circle of radius `radius` about its own centre, seen from the start pose: chord and heading
            swept = step * math.radians(9)
            self.assertAlmostEqual(math.hypot(pos[0], pos[1]), 2 * radius * math.sin(swept / 2), places=9)
            self.assertAlmostEqual(yaw, math.atan2(math.sin(swept), math.cos(swept)), places=9)

    def test_wrong_frame_names_are_refused(self):
        bridge.check_frames("camera_init", "aft_mapped")
        for frame, child in (("map", "aft_mapped"), ("camera_init", "base_link"), ("", ""), ("camera_init", "")):
            with self.assertRaises(ValueError):
                bridge.check_frames(frame, child)


if __name__ == "__main__":
    unittest.main()
