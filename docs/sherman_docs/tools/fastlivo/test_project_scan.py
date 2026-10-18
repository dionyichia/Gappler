#!/usr/bin/env python3
"""Tests for project_scan.py's pure logic.

Only the two bag-reading functions need the lab ROS environment; the
projection math, pairing, colour ramp and PNG writer are stdlib, so these
tests run anywhere:

    cd docs/sherman_docs/tools/fastlivo
    python3 -m unittest -v test_project_scan
"""
from __future__ import annotations

import hashlib
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import project_scan as tool  # noqa: E402
from check_replay_configs import NOMINAL_PCL, NOMINAL_RCL  # noqa: E402

IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
ZERO_T = (0.0, 0.0, 0.0)
NO_DISTORTION = (0.0, 0.0, 0.0, 0.0)

# The real t35b_proof3 camera values (replay/config/t35b_proof3_camera.yaml).
CAM_OK = {
    "cam_width": 640,
    "cam_height": 480,
    "cam_fx": 385.0851135253906,
    "cam_fy": 384.5696105957031,
    "cam_cx": 324.9161376953125,
    "cam_cy": 248.54244995117188,
    "cam_d0": -0.05590025335550308,
    "cam_d1": 0.06613793224096298,
    "cam_d2": 0.00020105774456169456,
    "cam_d3": 0.0002285563386976719,
}


class ProjectPointsTests(unittest.TestCase):
    def test_center_maps_to_principal_point(self):
        out = tool.project_points(
            [(0.0, 0.0, 2.0)], IDENTITY, ZERO_T, (100.0, 100.0, 50.0, 40.0),
            NO_DISTORTION, 640, 480, 0.1,
        )
        self.assertEqual(len(out), 1)
        u, v, depth = out[0]
        self.assertAlmostEqual(u, 50.0)
        self.assertAlmostEqual(v, 40.0)
        self.assertAlmostEqual(depth, 2.0)

    def test_hand_computed_offset(self):
        out = tool.project_points(
            [(0.1, 0.05, 0.5)], IDENTITY, ZERO_T, (100.0, 100.0, 50.0, 40.0),
            NO_DISTORTION, 640, 480, 0.1,
        )
        u, v, _ = out[0]
        self.assertAlmostEqual(u, 70.0)
        self.assertAlmostEqual(v, 50.0)

    def test_distortion_hand_computed(self):
        # xn=0.1, yn=0, r2=0.01 -> radial 1.00501; tangential adds
        # 0.3*(r2 + 2*xn^2) = 0.009 to xd and 0.2*r2 = 0.002 to yd.
        out = tool.project_points(
            [(0.1, 0.0, 1.0)], IDENTITY, ZERO_T, (100.0, 100.0, 0.0, 0.0),
            (0.5, 0.1, 0.2, 0.3), 640, 480, 0.1,
        )
        u, v, _ = out[0]
        self.assertAlmostEqual(u, 10.9501, places=6)
        self.assertAlmostEqual(v, 0.2, places=6)

    def test_behind_camera_and_zero_depth_rejected(self):
        out = tool.project_points(
            [(0.0, 0.0, -1.0), (0.0, 0.0, 0.0)], IDENTITY, ZERO_T,
            (100.0, 100.0, 0.0, 0.0), NO_DISTORTION, 640, 480, 0.1,
        )
        self.assertEqual(out, [])

    def test_min_depth_boundary_is_exclusive(self):
        out = tool.project_points(
            [(0.0, 0.0, 0.1), (0.0, 0.0, 0.1000001)], IDENTITY, ZERO_T,
            (100.0, 100.0, 0.0, 0.0), NO_DISTORTION, 640, 480, 0.1,
        )
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0][2], 0.1000001)

    def test_out_of_frame_rejected_at_edges(self):
        cases = (
            ((100.0, 100.0, -50.0, 0.0), "u < 0"),
            ((100.0, 100.0, 700.0, 0.0), "u >= width"),
            ((100.0, 100.0, 0.0, 500.0), "v >= height"),
        )
        for intrinsics, label in cases:
            with self.subTest(label):
                out = tool.project_points(
                    [(0.0, 0.0, 2.0)], IDENTITY, ZERO_T, intrinsics,
                    NO_DISTORTION, 640, 480, 0.1,
                )
                self.assertEqual(out, [])

    def test_pixel_zero_and_last_column_kept(self):
        out = tool.project_points(
            [(0.0, 0.0, 2.0)], IDENTITY, ZERO_T, (100.0, 100.0, 0.0, 0.0),
            NO_DISTORTION, 640, 480, 0.1,
        )
        self.assertEqual(len(out), 1)
        u, v, _ = out[0]
        self.assertAlmostEqual(u, 0.0)
        self.assertAlmostEqual(v, 0.0)

    def test_nominal_composition_forward_point(self):
        # 1 m straight ahead of the LiDAR under the reviewed nominal extrinsic:
        # p_cam = (0, 0, 1) + (-0.0115, 0.3425, -0.03915). With unit focal
        # lengths and principal point (1, 1) the point must land slightly left
        # of centre and clearly below it (the camera sits ~0.34 m above the
        # LiDAR), and its depth is 0.96085 m.
        out = tool.project_points(
            [(1.0, 0.0, 0.0)], list(NOMINAL_RCL), list(NOMINAL_PCL),
            (1.0, 1.0, 1.0, 1.0), NO_DISTORTION, 640, 480, 0.01,
        )
        self.assertEqual(len(out), 1)
        u, v, depth = out[0]
        self.assertAlmostEqual(depth, 0.96085, places=6)
        self.assertAlmostEqual(u, 0.9880314, places=6)
        self.assertAlmostEqual(v, 1.3564552, places=6)
        self.assertLess(u, 1.0)
        self.assertGreater(v, 1.3)


class PairingTests(unittest.TestCase):
    def test_nearest_exact_prefix_and_suffix(self):
        stamps = [100, 200, 300]
        self.assertEqual(tool.nearest_index(100, stamps), 0)
        self.assertEqual(tool.nearest_index(0, stamps), 0)
        self.assertEqual(tool.nearest_index(400, stamps), 2)

    def test_nearest_between_and_tie_earlier(self):
        stamps = [100, 200, 300]
        self.assertEqual(tool.nearest_index(260, stamps), 2)
        self.assertEqual(tool.nearest_index(250, stamps), 1)  # tie -> earlier

    def test_nearest_empty(self):
        self.assertIsNone(tool.nearest_index(100, []))

    def test_spread_matches_documented_selection(self):
        self.assertEqual(tool.spread_indices(740, 8), [0, 106, 211, 317, 422, 528, 633, 739])

    def test_spread_odd_shapes(self):
        self.assertEqual(tool.spread_indices(10, 3), [0, 5, 9])
        self.assertEqual(tool.spread_indices(10, 10), list(range(10)))
        self.assertEqual(tool.spread_indices(10, 20), list(range(10)))
        self.assertEqual(tool.spread_indices(5, 1), [2])
        self.assertEqual(tool.spread_indices(0, 3), [])


class DepthColorTests(unittest.TestCase):
    def test_ramp_endpoints_and_midpoints(self):
        self.assertEqual(tool.depth_color(0.0), (0, 0, 255))
        self.assertEqual(tool.depth_color(0.25), (0, 255, 255))
        self.assertEqual(tool.depth_color(0.5), (0, 255, 0))
        self.assertEqual(tool.depth_color(1.0), (255, 0, 0))

    def test_ramp_clamps_outside_values(self):
        self.assertEqual(tool.depth_color(-1.0), (0, 0, 255))
        self.assertEqual(tool.depth_color(2.0), (255, 0, 0))

    def test_normalization_percentile_pins(self):
        depths = [float(value) for value in range(1, 102)]  # 1.0 .. 101.0
        norms = tool.depth_normalized(depths)
        self.assertAlmostEqual(norms[5], 0.0)  # depth 6.0 == 5th percentile
        self.assertAlmostEqual(norms[50], 0.5)  # depth 51.0 == midpoint
        self.assertAlmostEqual(norms[95], 1.0)  # depth 96.0 == 95th percentile
        self.assertAlmostEqual(norms[0], 0.0)  # 1.0 clamps to 0
        self.assertAlmostEqual(norms[100], 1.0)  # 101.0 clamps to 1

    def test_normalization_degenerate_constant_depth(self):
        self.assertEqual(tool.depth_normalized([2.0, 2.0, 2.0]), [0.0, 0.0, 0.0])
        self.assertEqual(tool.depth_normalized([]), [])


class CameraConfigTests(unittest.TestCase):
    def test_read_camera_values(self):
        intrinsics, distortion = tool.read_camera(CAM_OK, 640, 480)
        self.assertEqual(
            intrinsics,
            (385.0851135253906, 384.5696105957031, 324.9161376953125, 248.54244995117188),
        )
        self.assertEqual(
            distortion,
            (-0.05590025335550308, 0.06613793224096298, 0.00020105774456169456, 0.0002285563386976719),
        )

    def test_read_camera_dimension_mismatch_raises(self):
        with self.assertRaises(ValueError):
            tool.read_camera(CAM_OK, 1280, 720)

    def test_read_camera_missing_or_bool_key_raises(self):
        missing = dict(CAM_OK)
        del missing["cam_d2"]
        with self.assertRaises(ValueError):
            tool.read_camera(missing, 640, 480)
        boolean = dict(CAM_OK, cam_fx=True)
        with self.assertRaises(ValueError):
            tool.read_camera(boolean, 640, 480)


class RequireVisualTests(unittest.TestCase):
    VISUAL = {
        "common.img_en": 1,
        "extrin_calib.Rcl": list(NOMINAL_RCL),
        "extrin_calib.Pcl": list(NOMINAL_PCL),
    }

    def test_accepts_nominal_visual_section(self):
        tool.require_visual(dict(self.VISUAL))  # must not raise

    def test_rejects_diagnostic_mode(self):
        with self.assertRaises(ValueError):
            tool.require_visual({"common.img_en": 0, "extrin_calib.Rcl": [1.0] * 9, "extrin_calib.Pcl": [0.0] * 3})

    def test_rejects_non_nominal_extrinsics(self):
        section = dict(self.VISUAL, **{"extrin_calib.Rcl": [0.0] * 9})
        with self.assertRaises(ValueError):
            tool.require_visual(section)


class PngWriterTests(unittest.TestCase):
    def test_round_trip_2x2(self):
        pixels = bytes([
            255, 0, 0, 0, 255, 0,
            0, 0, 255, 255, 255, 255,
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.png"
            tool.write_png(path, 2, 2, pixels)
            data = path.read_bytes()

        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        chunks = []
        position = 8
        while position < len(data):
            length = struct.unpack(">I", data[position : position + 4])[0]
            tag = data[position + 4 : position + 8]
            payload = data[position + 8 : position + 8 + length]
            crc = struct.unpack(">I", data[position + 8 + length : position + 12 + length])[0]
            self.assertEqual(crc, zlib.crc32(tag + payload) & 0xFFFFFFFF)
            chunks.append((tag, payload))
            position += 12 + length
        self.assertEqual([tag for tag, _ in chunks], [b"IHDR", b"IDAT", b"IEND"])

        width, height, depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunks[0][1])
        self.assertEqual((width, height, depth, color_type), (2, 2, 8, 2))
        raw = zlib.decompress(chunks[1][1])
        self.assertEqual(raw[0], 0)  # filter type of the first scanline
        self.assertEqual(raw[1:7], pixels[:6])
        self.assertEqual(raw[7], 0)
        self.assertEqual(raw[8:14], pixels[6:])

    def test_wrong_payload_length_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                tool.write_png(Path(tmp) / "bad.png", 2, 2, bytes(11))

    def test_default_level_bytes_are_pinned(self):
        # Evidence overlays were produced at the default compression level;
        # keep the default byte-for-byte reproducible.
        pixels = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.png"
            tool.write_png(path, 2, 2, pixels)
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                "e6d66889131220f931fddfb05730d647a0992456c63ae0a8154b4ae32ff219ef",
            )

    def test_faster_level_writes_same_pixels(self):
        # live_preview.py passes level=1 to keep its render cheap.
        pixels = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fast.png"
            tool.write_png(path, 2, 2, pixels, level=1)
            data = path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        header_length = struct.unpack(">I", data[8:12])[0]
        self.assertEqual(data[12:16], b"IHDR")
        idat_start = 8 + 12 + header_length
        idat_length = struct.unpack(">I", data[idat_start : idat_start + 4])[0]
        self.assertEqual(data[idat_start + 4 : idat_start + 8], b"IDAT")
        raw = zlib.decompress(data[idat_start + 8 : idat_start + 8 + idat_length])
        self.assertEqual(
            raw,
            bytes([0, 255, 0, 0, 0, 255, 0, 0, 0, 0, 255, 255, 255, 255]),
        )


class StampTests(unittest.TestCase):
    def test_stamp_nanoseconds(self):
        stamp = SimpleNamespace(sec=3, nanosec=500)
        self.assertEqual(tool._stamp_ns(stamp), 3_000_000_500)


if __name__ == "__main__":
    unittest.main()
