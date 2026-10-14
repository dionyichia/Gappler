"""The recording checker (T6.2a).

Each test writes a small rosbag2 recording of its own: a base driving two laps
of a 3 m circle, with colour, aligned depth, camera info, LiDAR and TF, shaped
like the base camera launch and the localisation stack. The good one must pass.
Each bad one breaks one thing a real drive could get wrong, and the checker
must name it.
"""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

try:
    from rosbags.rosbag2 import Writer
    from rosbags.typesys import Stores, get_typestore
except ImportError as exc:  # pragma: no cover - depends on the machine
    raise unittest.SkipTest(f"needs rosbags: {exc}")

from memory_graph.recording_check import FAIL, PASS, WARN, RecordingSpec, check_recording, header_stamp, main

TS = get_typestore(Stores.ROS2_HUMBLE)
SPEC = RecordingSpec()
H, W = 6, 8
CAMERA = "base_d455_color_optical_frame"
SECONDS = 80.0     # two laps of 40 s each, so the second lap revisits the first


def _stamp(t):
    sec = int(t)
    return TS.types["builtin_interfaces/msg/Time"](sec=sec, nanosec=int(round((t - sec) * 1e9)))


def _header(t, frame):
    return TS.types["std_msgs/msg/Header"](stamp=_stamp(t), frame_id=frame)


def _image(t, frame, encoding, w=W, h=H, fill=1000):
    if encoding == "16UC1":
        data = np.full(h * w, fill, dtype=np.uint16).view(np.uint8)
        step = w * 2
    else:
        data = np.zeros(h * w * 3, dtype=np.uint8)
        step = w * 3
    return TS.types["sensor_msgs/msg/Image"](
        header=_header(t, frame), height=h, width=w, encoding=encoding, is_bigendian=0, step=step, data=data)


def _info(t):
    roi = TS.types["sensor_msgs/msg/RegionOfInterest"](x_offset=0, y_offset=0, height=0, width=0, do_rectify=False)
    k = np.array([5.0, 0, W / 2, 0, 5.0, H / 2, 0, 0, 1])
    return TS.types["sensor_msgs/msg/CameraInfo"](
        header=_header(t, CAMERA), height=H, width=W, distortion_model="plumb_bob", d=np.zeros(5),
        k=k, r=np.eye(3).ravel(), p=np.zeros(12), binning_x=0, binning_y=0, roi=roi)


def _cloud(t):
    return TS.types["sensor_msgs/msg/PointCloud2"](
        header=_header(t, "livox_frame"), height=1, width=0, fields=[], is_bigendian=False,
        point_step=0, row_step=0, data=np.zeros(0, dtype=np.uint8), is_dense=True)


def _tf(t, parent, child, xyz=(0.0, 0.0, 0.0), yaw=0.0):
    msg = TS.types
    transform = msg["geometry_msgs/msg/Transform"](
        translation=msg["geometry_msgs/msg/Vector3"](x=xyz[0], y=xyz[1], z=xyz[2]),
        rotation=msg["geometry_msgs/msg/Quaternion"](x=0.0, y=0.0, z=math.sin(yaw / 2), w=math.cos(yaw / 2)))
    return msg["geometry_msgs/msg/TransformStamped"](header=_header(t, parent), child_frame_id=child, transform=transform)


def write_bag(path, *, image_hz=10.0, aligned=True, map_odom=True, lidar=True, gap=None, radius=1.5):
    """A drive of two laps round a circle. `gap` is (start, end) seconds with no images."""
    tfm = "tf2_msgs/msg/TFMessage"
    with Writer(path, version=8) as w:
        color = w.add_connection(SPEC.color_topic, "sensor_msgs/msg/Image", typestore=TS)
        depth = w.add_connection(SPEC.depth_topic, "sensor_msgs/msg/Image", typestore=TS)
        info = w.add_connection(SPEC.info_topic, "sensor_msgs/msg/CameraInfo", typestore=TS)
        tf = w.add_connection("/tf", tfm, typestore=TS)
        static = w.add_connection("/tf_static", tfm, typestore=TS)
        cloud = w.add_connection(SPEC.lidar_topic, "sensor_msgs/msg/PointCloud2", typestore=TS) if lidar else None

        def put(conn, t, msg, msgtype):
            w.write(conn, int(t * 1e9), TS.serialize_cdr(msg, msgtype))

        put(static, 0.0, TS.types[tfm](transforms=[
            _tf(0.0, "robot_base_link", "base_d455_bottom_screw_frame", (0.208, 0.0, 0.528)),
            _tf(0.0, "base_d455_bottom_screw_frame", "base_d455_link"),
            _tf(0.0, "base_d455_link", CAMERA),
        ]), tfm)
        for i in range(int(SECONDS * 20)):              # TF at 20 Hz
            t = i / 20
            a = 2 * math.pi * t / (SECONDS / 2)
            edges = [_tf(t, "odom", "robot_base_link", (radius * math.cos(a), radius * math.sin(a), 0.0), a)]
            if map_odom:
                edges.append(_tf(t, "map", "odom"))
            put(tf, t, TS.types[tfm](transforms=edges), tfm)
        for i in range(int(SECONDS * 10)):              # LiDAR at 10 Hz
            if cloud:
                put(cloud, i / 10, _cloud(i / 10), "sensor_msgs/msg/PointCloud2")
        for i in range(int(SECONDS * image_hz)):
            t = i / image_hz
            if gap and gap[0] <= t < gap[1]:
                continue
            put(color, t, _image(t, CAMERA, "rgb8"), "sensor_msgs/msg/Image")
            if aligned:
                put(depth, t, _image(t, CAMERA, "16UC1"), "sensor_msgs/msg/Image")
            else:
                put(depth, t, _image(t, "base_d455_depth_optical_frame", "16UC1", w=W + 2), "sensor_msgs/msg/Image")
            put(info, t, _info(t), "sensor_msgs/msg/CameraInfo")


class RecordingCheckTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def run_check(self, **kwargs):
        bag = self.tmp / "bag"
        write_bag(bag, **kwargs)
        report = check_recording(bag)
        return report, {c.name: c for c in report.checks}

    def test_a_good_drive_passes(self):
        report, checks = self.run_check()
        self.assertFalse(report.failed, report.text())
        for name in ("colour images", "aligned depth", "LiDAR", "depth aligned to colour",
                     "poses", "route length", "revisits", "camera mount", "intrinsics"):
            self.assertEqual(checks[name].status, PASS, f"{name}: {checks[name].detail}")
        self.assertIn("base_d455_bottom_screw_frame", checks["camera mount"].detail)

    def test_raw_depth_instead_of_aligned_fails(self):
        report, checks = self.run_check(aligned=False)
        self.assertTrue(report.failed)
        self.assertEqual(checks["depth aligned to colour"].status, FAIL)
        self.assertIn("align_depth.enable", checks["depth aligned to colour"].detail)

    def test_no_localisation_fails(self):
        report, checks = self.run_check(map_odom=False)
        self.assertEqual(checks["poses"].status, FAIL)
        self.assertIn("map -> odom", checks["poses"].detail)

    def test_missing_lidar_fails(self):
        _, checks = self.run_check(lidar=False)
        self.assertEqual(checks["LiDAR"].status, FAIL)

    def test_too_slow_images_fail(self):
        _, checks = self.run_check(image_hz=2.0)
        self.assertEqual(checks["colour images"].status, FAIL)

    def test_dropped_frames_warn(self):
        report, checks = self.run_check(gap=(10.0, 13.0))
        self.assertEqual(checks["colour images"].status, WARN)
        self.assertFalse(report.failed, report.text())

    def test_a_drive_that_never_comes_back_warns(self):
        bag = self.tmp / "bag"
        write_bag(bag)
        report = check_recording(bag, replace(SPEC, revisit_after_s=1000.0))
        self.assertEqual({c.name: c for c in report.checks}["revisits"].status, WARN)

    def test_a_short_drive_fails(self):
        report, checks = self.run_check(radius=0.05)
        self.assertEqual(checks["route length"].status, FAIL)

    def test_header_stamp_reads_little_and_big_endian(self):
        msg = _image(12.25, CAMERA, "rgb8")
        raw = bytes(TS.serialize_cdr(msg, "sensor_msgs/msg/Image"))
        self.assertAlmostEqual(header_stamp(raw), 12.25, places=6)
        raw_be = bytes(TS.serialize_cdr(msg, "sensor_msgs/msg/Image", little_endian=False))
        self.assertAlmostEqual(header_stamp(raw_be), 12.25, places=6)

    def test_command_line_exit_codes(self):
        good, bad = self.tmp / "good", self.tmp / "bad"
        write_bag(good)
        write_bag(bad, aligned=False)
        with open(self.tmp / "out.txt", "w") as out:
            import contextlib
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                self.assertEqual(main([str(good)]), 0)
                self.assertEqual(main([str(bad)]), 1)
                self.assertEqual(main([str(self.tmp / "no_such_bag")]), 2)


if __name__ == "__main__":
    unittest.main()
