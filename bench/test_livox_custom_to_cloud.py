"""CustomMsg to PointCloud2 converter: the decoder against real bytes (stdlib, no ROS). The numpy fast path runs when numpy exists.

Why a hand decoder: decoding one 19,968-point CustomMsg with rclpy takes 110.6 ms on the box, longer than the LiDAR period,
while the numpy decode takes 0.38 ms and equals rclpy field for field (T3.5e write-up, Phase 1).
"""
import importlib.util
import json
import math
from pathlib import Path
import struct
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("livox_custom_to_cloud", REPO / "nav/robot_slam/scripts/livox_custom_to_cloud.py")
conv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conv)
FIXTURES = json.loads((REPO / "bench/golden/livox_custom_msg.json").read_text())["fixtures"]


def point_tuples(fixture):
    return [tuple(p) for p in fixture["points"]]


class DecoderTests(unittest.TestCase):
    def test_reference_decoder_equals_what_rclpy_decodes_from_the_same_bytes(self):
        for fx in FIXTURES:
            msg = conv.decode_custom_msg(bytes.fromhex(fx["cdr_hex"]))
            self.assertEqual((msg["sec"], msg["nanosec"], msg["frame_id"]), (fx["sec"], fx["nanosec"], fx["frame_id"]))
            self.assertEqual((msg["timebase"], msg["point_num"], msg["lidar_id"]), (fx["timebase"], fx["point_num"], fx["lidar_id"]))
            self.assertEqual(msg["points"], point_tuples(fx), "%d points" % fx["points_wanted"])

    def test_fixtures_cover_many_one_and_zero_points(self):
        self.assertEqual(sorted(f["points_wanted"] for f in FIXTURES), [0, 1, 40])

    def test_truncated_or_short_buffers_are_refused(self):
        raw = bytes.fromhex(FIXTURES[0]["cdr_hex"])
        for cut in (3, 20, len(raw) - 25, len(raw) - 2):
            with self.assertRaises(ValueError, msg="cut to %d bytes" % cut):
                conv.decode_custom_msg(raw[:cut])

    def test_cloud_bytes_are_x_y_z_intensity_float32_in_16_byte_points(self):
        points = [(0, 1.5, -2.0, 0.25, 200, 0, 1), (0, 3.0, 4.0, 5.0, 7, 0, 2)]
        data = conv.cloud_bytes(points)
        self.assertEqual(len(data), 2 * conv.POINT_STEP)
        self.assertEqual(conv.POINT_STEP, 16)
        self.assertEqual(struct.unpack_from("<ffff", data, 0), (1.5, -2.0, 0.25, 200.0))
        self.assertEqual(struct.unpack_from("<ffff", data, 16), (3.0, 4.0, 5.0, 7.0))
        self.assertEqual([(f[0], f[1]) for f in conv.FIELDS], [("x", 0), ("y", 4), ("z", 8), ("intensity", 12)])

    def test_non_finite_points_are_dropped_not_passed_on(self):
        points = [(0, math.nan, 0.0, 0.0, 1, 0, 0), (0, 1.0, 2.0, 3.0, 9, 0, 0), (0, math.inf, 0.0, 0.0, 1, 0, 0)]
        data = conv.cloud_bytes(points)
        self.assertEqual(len(data), conv.POINT_STEP)
        self.assertEqual(struct.unpack("<ffff", data), (1.0, 2.0, 3.0, 9.0))

    def test_frame_id_lengths_that_need_alignment_padding(self):
        """Build CDR by hand for frame_id lengths 1 to 9 (the real one, livox_frame, happens to need no padding)."""
        points = [(7, 1.0, 2.0, 3.0, 4, 5, 6), (8, -1.0, -2.0, -3.0, 9, 10, 11), (9, 0.5, 0.25, 0.125, 1, 2, 3)]
        for length in range(1, 10):
            frame = "f" * length
            raw = bytearray(b"\x00\x01\x00\x00")  # encapsulation header, little endian
            body = bytearray(struct.pack("<iII", 12, 345, length + 1) + frame.encode() + b"\0")
            body += b"\0" * (-len(body) % 8)  # timebase is 8-byte aligned
            body += struct.pack("<QIB3x", 1234567890123, len(points), 3)
            body += struct.pack("<I", len(points))
            for i, pt in enumerate(points):
                body += struct.pack("<IfffBBB", *pt) + (b"\0" if i < len(points) - 1 else b"")  # no pad after the last point
            msg = conv.decode_custom_msg(bytes(raw + body))
            self.assertEqual((msg["frame_id"], msg["sec"], msg["nanosec"], msg["timebase"], msg["lidar_id"]), (frame, 12, 345, 1234567890123, 3), length)
            self.assertEqual(msg["points"], points, "frame_id length %d" % length)

    def test_numpy_fast_path_equals_the_reference_on_every_fixture(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy not installed here; runs on the lab box")
        for fx in FIXTURES:
            raw = bytes.fromhex(fx["cdr_hex"])
            ref = conv.decode_custom_msg(raw)
            fast = conv.decode_custom_msg_numpy(raw)
            self.assertEqual((fast["sec"], fast["nanosec"], fast["frame_id"], fast["timebase"], fast["point_num"]),
                             (ref["sec"], ref["nanosec"], ref["frame_id"], ref["timebase"], ref["point_num"]))
            self.assertEqual([tuple(float(v) for v in row) for row in fast["array"].tolist()], [tuple(float(v) for v in p) for p in ref["points"]])
            self.assertEqual(conv.cloud_bytes_numpy(fast["array"]), conv.cloud_bytes(ref["points"]))


if __name__ == "__main__":
    unittest.main()
