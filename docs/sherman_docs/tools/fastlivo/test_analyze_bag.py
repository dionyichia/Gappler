#!/usr/bin/env python3
"""Positive and negative tests for analyze_bag.py using synthetic mini-bags.

Every case builds a tiny sqlite bag in a temp directory, runs the analyser as
a subprocess and asserts the exit code plus the diagnostic text. The last case
proves the analyser still passes a bag that satisfies every invariant, so the
failure assertions cannot be satisfied by a tool that always fails.

Requires the lab ROS environment (rosbag2_py, livox_ros_driver2, sensor_msgs):
    source /opt/ros/humble/setup.bash
    source ~/rcp-Gappler/install_nav/setup.bash
    cd docs/sherman_docs/tools/fastlivo
    python3 -m unittest -v test_analyze_bag
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import rosbag2_py
from rclpy.serialization import serialize_message
from sensor_msgs.msg import CameraInfo, Image, Imu
from livox_ros_driver2.msg import CustomMsg, CustomPoint

HERE = Path(__file__).resolve().parent
ANALYZER = HERE / "analyze_bag.py"

NS = 1_000_000_000
LIDAR = "/livox/lidar"
IMU = "/livox/imu"
IMAGE = "/camera/camera/color/image_raw"
CAMINFO = "/camera/camera/color/camera_info"
TYPEMAP = {LIDAR: CustomMsg, IMU: Imu, IMAGE: Image, CAMINFO: CameraInfo}


def _set_stamp(msg, stamp_ns: int, frame: str) -> None:
    msg.header.stamp.sec = stamp_ns // NS
    msg.header.stamp.nanosec = stamp_ns % NS
    msg.header.frame_id = frame


def _point(x: float, y: float, z: float, offset_ns: int, line: int = 0) -> CustomPoint:
    p = CustomPoint()
    p.x, p.y, p.z = x, y, z
    p.reflectivity = 1
    p.tag = 0
    p.line = line
    p.offset_time = offset_ns
    return p


def _lidar(stamp_ns: int, points: list, point_num: int | None) -> CustomMsg:
    m = CustomMsg()
    _set_stamp(m, stamp_ns, "livox_frame")
    m.timebase = stamp_ns
    m.point_num = len(points) if point_num is None else point_num
    m.lidar_id = 192
    m.points = points
    return m


def _imu(stamp_ns: int) -> Imu:
    m = Imu()
    _set_stamp(m, stamp_ns, "livox_frame")
    m.orientation.w = 1.0
    m.angular_velocity.x = 0.001
    m.angular_velocity.y = -0.001
    m.angular_velocity.z = 0.002
    m.linear_acceleration.x = 0.01
    m.linear_acceleration.y = -0.02
    m.linear_acceleration.z = 0.99
    return m


def _image(stamp_ns: int) -> Image:
    m = Image()
    _set_stamp(m, stamp_ns, "camera_color_optical_frame")
    m.height, m.width, m.step = 1, 2, 6
    m.encoding = "rgb8"
    m.is_bigendian = 0
    m.data = b"\x00" * (m.step * m.height)
    return m


def _caminfo(stamp_ns: int) -> CameraInfo:
    m = CameraInfo()
    _set_stamp(m, stamp_ns, "camera_color_optical_frame")
    m.height, m.width = 1, 2
    m.distortion_model = "plumb_bob"
    m.k = [1.0, 0.0, 1.0, 0.0, 1.0, 0.5, 0.0, 0.0, 1.0]
    m.d = [0.0, 0.0, 0.0, 0.0, 0.0]
    m.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    m.p = [1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.5, 0.0, 0.0, 0.0, 1.0, 0.0]
    return m


def _write_bag(uri: Path, messages: list) -> None:
    writer = rosbag2_py.SequentialWriter()
    writer.open(
        rosbag2_py.StorageOptions(uri=str(uri), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    for topic in TYPEMAP:
        writer.create_topic(
            rosbag2_py.TopicMetadata(
                name=topic,
                type=f"{TYPEMAP[topic].__module__}/msg/{TYPEMAP[topic].__name__}",
                serialization_format="cdr",
            )
        )
    for topic, msg, write_ns in messages:
        writer.write(topic, serialize_message(msg), write_ns)


class AnalyzeBagTests(unittest.TestCase):
    maxDiff = None

    def _build(self, *, lidar_stamps=None, drop_last_caminfo=False,
               nan_point=False, point_num_lie=False) -> Path:
        tmpdir = Path(tempfile.mkdtemp(prefix="t35-bag-"))
        self.addCleanup(shutil.rmtree, tmpdir, True)
        bag = tmpdir / "bag"

        t0 = 1_000 * NS
        if lidar_stamps is None:
            lidar_stamps = [t0 + 100_000_000, t0 + 200_000_000]
        points = [_point(1.0, 2.0, 3.0, 0),
                  _point(0.0, 0.0, 0.0, 5_000_000),
                  _point(4.0, 5.0, 6.0, 10_000_000, line=1)]
        if nan_point:
            points[1] = _point(float("nan"), 0.0, 0.0, 5_000_000)
        point_num = len(points) + 1 if point_num_lie else None

        messages = []
        prev_lidar_write = 0
        for stamp in lidar_stamps:
            # Readers return messages ordered by record time: clamp the record
            # timestamps monotonic so deliberately corrupted header order is
            # still read back in the written order.
            write_ns = max(stamp + 100_000_000, prev_lidar_write + 1)
            prev_lidar_write = write_ns
            messages.append((LIDAR, _lidar(stamp, points, point_num), write_ns))
        for i in range(4):
            stamp = t0 + i * 5_000_000
            messages.append((IMU, _imu(stamp), stamp))
        for i in range(2):
            stamp = t0 + i * 33_000_000
            messages.append((IMAGE, _image(stamp), stamp + 30_000_000))
            if drop_last_caminfo and i == 1:
                continue
            messages.append((CAMINFO, _caminfo(stamp), stamp + 30_000_000))

        _write_bag(bag, messages)
        return bag

    def _run(self, bag: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ANALYZER), str(bag)],
            capture_output=True, text=True, timeout=180,
        )

    def test_valid_mini_bag_passes(self) -> None:
        proc = self._run(self._build())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(proc.stdout.strip().splitlines()[-1] == "ANALYSIS_OK")

    def test_backward_lidar_stamp_fails(self) -> None:
        t0 = 1_000 * NS
        bag = self._build(lidar_stamps=[t0 + 100_000_000, t0 + 50_000_000])
        proc = self._run(bag)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("lidar header stamps not strictly increasing", proc.stdout)
        self.assertIn("1 backwards", proc.stdout)
        self.assertIn("ANALYSIS_FAILED", proc.stdout)

    def test_duplicate_lidar_stamp_fails(self) -> None:
        t0 = 1_000 * NS
        bag = self._build(lidar_stamps=[t0 + 100_000_000, t0 + 100_000_000])
        proc = self._run(bag)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("1 duplicates", proc.stdout)

    def test_missing_caminfo_fails(self) -> None:
        proc = self._run(self._build(drop_last_caminfo=True))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("image/caminfo count mismatch", proc.stdout)

    def test_non_finite_lidar_point_fails(self) -> None:
        proc = self._run(self._build(nan_point=True))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("non-finite XYZ", proc.stdout)

    def test_point_num_mismatch_fails(self) -> None:
        proc = self._run(self._build(point_num_lie=True))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("point_num mismatch", proc.stdout)


if __name__ == "__main__":
    unittest.main()
