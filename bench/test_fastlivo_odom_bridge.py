"""The FAST-LIVO2 to odom -> robot_base_link transform, checked with plain trigonometry (stdlib, no ROS).

The mapper reports the IMU body pose in camera_init. The bridge must turn that into the robot_base_link
pose in an odom frame that equals robot_base_link at startup, whatever tilt camera_init has.
"""
import importlib.util
import json
import math
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fastlivo_odom_bridge", REPO / "nav/robot_slam/scripts/fastlivo_odom_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

CONFIG = (REPO / "nav/robot_slam/config/fastlivo_bridge.yaml").read_text()


def config_value(key):
    """One flow-style value from the parameter file (stdlib, no PyYAML)."""
    return json.loads(re.search(r"^\s*%s:\s*(.+?)\s*(?:#.*)?$" % re.escape(key), CONFIG, re.M).group(1).replace("'", '"'))


OFFSET = tuple(config_value("body_in_base_m"))  # IMU body origin in robot_base_link, identity rotation, from the config file


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
        odom = bridge.OdomFromMapper(OFFSET)
        pos, q = odom.update(*body_pose(mm(rz(0.5), mm(ry(0.02), rx(-0.01))), (3.0, -2.0, 0.4)))
        for v in pos:
            self.assertAlmostEqual(v, 0.0, places=9)
        self.assertAlmostEqual(abs(q[3]), 1.0, places=9)

    def test_straight_drive_moves_the_base_along_its_own_forward(self):
        odom = bridge.OdomFromMapper(OFFSET)
        start_yaw = math.radians(30)  # robot starts facing 30 degrees in camera_init
        odom.update(*body_pose(rz(start_yaw), (1.0, 2.0, 0.0)))
        d = 0.8
        pos, q = odom.update(*body_pose(rz(start_yaw), (1.0 + d * math.cos(start_yaw), 2.0 + d * math.sin(start_yaw), 0.0)))
        self.assertAlmostEqual(pos[0], d, places=9)
        self.assertAlmostEqual(pos[1], 0.0, places=9)
        self.assertAlmostEqual(yaw_pitch_roll(q)[0], 0.0, places=9)

    def test_turning_in_place_about_the_base_centre_does_not_move_the_base(self):
        odom = bridge.OdomFromMapper(OFFSET)
        odom.update(*body_pose(rz(0.0), (0.0, 0.0, 0.0)))
        for deg in (10, 90, 179, -120, 360):
            pos, q = odom.update(*body_pose(rz(math.radians(deg)), (0.0, 0.0, 0.0)))
            for v in pos:
                self.assertAlmostEqual(v, 0.0, places=9, msg="%d deg" % deg)
            want = math.atan2(math.sin(math.radians(deg)), math.cos(math.radians(deg)))
            self.assertAlmostEqual(yaw_pitch_roll(q)[0], want, places=9)

    def test_startup_tilt_of_camera_init_cancels_and_a_level_drive_stays_level(self):
        tilt = mm(ry(math.radians(-0.4)), rx(math.radians(0.73)))  # the 0.7 degree start tilt seen in the T3.5d bags
        odom = bridge.OdomFromMapper(OFFSET)
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

    def test_config_notes_the_move_to_global_config_after_approval(self):
        self.assertIn("global_config", CONFIG)
        self.assertIn("Dion", CONFIG)
        self.assertNotIn("BODY_IN_BASE =", (REPO / "nav/robot_slam/scripts/fastlivo_odom_bridge.py").read_text())

    def test_startup_tilt_guard_refuses_a_robot_that_did_not_start_level(self):
        ok = bridge.OdomFromMapper(OFFSET, max_startup_tilt_deg=2.0)
        ok.update(*body_pose(mm(ry(math.radians(0.4)), rx(math.radians(0.73))), (0.0, 0.0, 0.0)))  # the 0.73 deg seen in T3.5d
        tilted = bridge.OdomFromMapper(OFFSET, max_startup_tilt_deg=2.0)
        for rot in (rx(math.radians(2.5)), ry(math.radians(-3.0))):
            with self.assertRaises(bridge.StartupTiltError):
                tilted.update(*body_pose(rot, (0.0, 0.0, 0.0)))
            self.assertIsNone(tilted._r0, "a refused startup must not become the reference")

    def test_a_jump_between_samples_is_a_mapper_restart_and_is_refused(self):
        odom = bridge.OdomFromMapper(OFFSET, max_jump_m=0.5)
        odom.update(*body_pose(rz(0.0), (0.0, 0.0, 0.0)))
        odom.update(*body_pose(rz(0.0), (0.04, 0.0, 0.0)))  # 0.04 m between 20 Hz samples is fine
        with self.assertRaises(bridge.MapperJumpError):
            odom.update(*body_pose(rz(0.0), (3.0, 0.0, 0.0)))
        odom.reset()  # an operator restart accepts the new origin
        odom.update(*body_pose(rz(0.0), (3.0, 0.0, 0.0)))

    def test_stale_gate_stops_publishing_when_the_mapper_goes_quiet(self):
        gate = bridge.FreshnessGate(window_s=0.5)
        self.assertFalse(gate.fresh(now=10.0), "nothing received yet is stale")
        gate.received(10.0)
        self.assertTrue(gate.fresh(now=10.4))
        self.assertFalse(gate.fresh(now=10.6))
        gate.received(10.7)
        self.assertTrue(gate.fresh(now=10.8))

    def test_twist_is_in_the_base_frame_and_zero_when_still(self):
        pose = lambda yaw, x, y: (rz(yaw), [x, y, 0.0])
        dt, yaw = 0.05, math.radians(30)
        a = pose(yaw, 1.0, 2.0)
        b = pose(yaw, 1.0 + 0.5 * dt * math.cos(yaw), 2.0 + 0.5 * dt * math.sin(yaw))  # 0.5 m/s along its own forward
        v, w = bridge.twist_between(a, b, dt)
        self.assertAlmostEqual(v[0], 0.5, places=9)
        self.assertAlmostEqual(v[1], 0.0, places=9)
        c = pose(yaw + 0.3 * dt, 1.0, 2.0)  # turning 0.3 rad/s in place
        v, w = bridge.twist_between(a, c, dt)
        self.assertAlmostEqual(w[2], 0.3, places=9)
        self.assertAlmostEqual(math.hypot(*v), 0.0, places=9)
        v, w = bridge.twist_between(a, a, dt)
        self.assertEqual((v, w), ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0]))

    def test_only_the_final_pose_of_each_scan_is_published(self):
        """Visual mode publishes twice per scan: after the partial LIO update (before the visual correction), then after the final one.

        Measured on handdriven1: gaps between the two are 0 to 50 ms, between scans 55 to 100 ms (T3.5e write-up)."""
        sel = bridge.ScanPairSelector(window_s=0.05)
        out = []
        for t, name in ((0.000, "a1"), (0.014, "a2"), (0.100, "b1"), (0.113, "b2"), (0.201, "c1"), (0.214, "c2")):
            out += [(t, i) for i in sel.offer(t, name)]
        self.assertEqual([i for _, i in out], ["a2", "b2", "c2"])
        self.assertEqual([t for t, _ in out], [0.014, 0.113, 0.214], "the final pose goes out the moment it arrives, no added delay")
        self.assertEqual(sel.poll(0.5), [], "nothing left pending after a pair")

    def test_a_scan_with_a_single_pose_is_published_after_the_window(self):
        sel = bridge.ScanPairSelector(window_s=0.05)
        self.assertEqual(sel.offer(0.0, "solo"), [])
        self.assertEqual(sel.poll(0.04), [], "still inside the window")
        self.assertEqual(sel.poll(0.06), ["solo"])
        self.assertEqual(sel.poll(0.2), [], "published once only")

    def test_a_single_pose_is_flushed_by_the_next_scans_first_message(self):
        sel = bridge.ScanPairSelector(window_s=0.05)
        sel.offer(0.0, "solo")
        self.assertEqual(sel.offer(0.1, "n1"), ["solo"])
        self.assertEqual(sel.offer(0.114, "n2"), ["n2"])

    def test_gap_equal_to_the_window_still_counts_as_the_same_scan_and_a_longer_one_does_not(self):
        sel = bridge.ScanPairSelector(window_s=0.05)
        sel.offer(0.0, "p1")
        self.assertEqual(sel.offer(0.05, "p2"), ["p2"])
        sel = bridge.ScanPairSelector(window_s=0.05)
        sel.offer(0.0, "q1")
        self.assertEqual(sel.offer(0.0501, "q2"), ["q1"], "too late to be a partner: a new scan")

    def test_three_poses_in_one_window_publish_the_later_two_never_the_first(self):
        sel = bridge.ScanPairSelector(window_s=0.05)
        out = sel.offer(0.0, "x1") + sel.offer(0.01, "x2") + sel.offer(0.02, "x3")
        self.assertEqual(out, ["x2", "x3"])

    def test_wrong_frame_names_are_refused(self):
        bridge.check_frames("camera_init", "aft_mapped")
        for frame, child in (("map", "aft_mapped"), ("camera_init", "base_link"), ("", ""), ("camera_init", "")):
            with self.assertRaises(ValueError):
                bridge.check_frames(frame, child)


if __name__ == "__main__":
    unittest.main()
