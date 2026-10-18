#!/usr/bin/env python3
"""Tests for live_preview.py's pure logic.

The rclpy subscriber path runs only on the lab box; rendering, stats, the
HTML page and config loading are stdlib, so these tests run anywhere:

    cd docs/sherman_docs/tools/fastlivo
    python3 -m unittest -v test_live_preview
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import live_preview as tool  # noqa: E402
from check_replay_configs import NOMINAL_PCL, NOMINAL_RCL  # noqa: E402

try:
    import yaml  # noqa: F401

    HAVE_YAML = True
except ImportError:  # config-file tests need PyYAML; the rest do not
    HAVE_YAML = False

IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
ZERO_T = (0.0, 0.0, 0.0)
NO_DISTORTION = (0.0, 0.0, 0.0, 0.0)
VISUAL_LIO = HERE / "replay" / "config" / "t35b_proof3_visual.yaml"
CAMERA_YAML = HERE / "replay" / "config" / "t35b_proof3_camera.yaml"


def gray_image(width: int, height: int, value: int = 100) -> bytes:
    return bytes([value]) * (width * height * 3)


@unittest.skipUnless(HAVE_YAML, "PyYAML not available")
class LoadConfigTests(unittest.TestCase):
    def test_real_visual_pair_loads_nominal_extrinsics(self):
        config = tool.load_config(VISUAL_LIO, CAMERA_YAML)
        self.assertEqual(config["rcl"], list(NOMINAL_RCL))
        self.assertEqual(config["pcl"], list(NOMINAL_PCL))
        self.assertGreater(config["blind"], 0.0)
        self.assertIn("camera", config)

    def test_non_visual_section_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "off.yaml"
            path.write_text("laserMapping:\n  ros__parameters:\n    img_en: 0\n")
            with self.assertRaises(ValueError):
                tool.load_config(path, CAMERA_YAML)

    def test_missing_blind_is_refused(self):
        text = VISUAL_LIO.read_text()
        stripped = "\n".join(
            line for line in text.splitlines() if "blind" not in line
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "noblind.yaml"
            path.write_text(stripped + "\n")
            with self.assertRaises(ValueError):
                tool.load_config(path, CAMERA_YAML)


class ToRgbBytesTests(unittest.TestCase):
    def test_rgb8_is_passed_through(self):
        data = bytes([1, 2, 3, 4, 5, 6])
        self.assertEqual(tool.to_rgb_bytes(data, "rgb8", 2, 1), data)

    def test_bgr8_swaps_channels(self):
        data = bytes([1, 2, 3, 4, 5, 6])
        self.assertEqual(tool.to_rgb_bytes(data, "bgr8", 2, 1), bytes([3, 2, 1, 6, 5, 4]))

    def test_unknown_encoding_raises(self):
        with self.assertRaises(ValueError):
            tool.to_rgb_bytes(bytes(6), "mono16", 2, 1)


class OverlayTests(unittest.TestCase):
    WIDTH = 64
    HEIGHT = 48
    INTRINSICS = (50.0, 50.0, 32.0, 24.0)

    def render(self, projected):
        return tool.overlay_rgb(
            gray_image(self.WIDTH, self.HEIGHT), self.WIDTH, self.HEIGHT, projected
        )

    def project(self, points):
        return tool.project_points(
            points, IDENTITY, ZERO_T, self.INTRINSICS, NO_DISTORTION,
            self.WIDTH, self.HEIGHT, 0.1,
        )

    def test_no_points_only_dims_background(self):
        out = self.render([])
        self.assertEqual(len(out), self.WIDTH * self.HEIGHT * 3)
        # 50% dim of 100 is 50 everywhere.
        self.assertEqual(set(out), {50})

    def test_front_point_paints_principal_pixel(self):
        projected = self.project([(0.0, 0.0, 2.0)])
        self.assertEqual(len(projected), 1)
        out = self.render(projected)
        pixel = (24 * self.WIDTH + 32) * 3
        self.assertNotEqual(out[pixel : pixel + 3], bytes([50, 50, 50]))

    def test_behind_camera_point_paints_nothing(self):
        projected = self.project([(0.0, 0.0, -1.0)])
        self.assertEqual(projected, [])
        self.assertEqual(self.render(projected), self.render([]))


class RegionCountTests(unittest.TestCase):
    def test_cells_and_total(self):
        width = height = 90
        projected = [
            (5.0, 5.0, 1.0),  # row 0, col 0
            (85.0, 5.0, 1.0),  # row 0, col 2
            (5.0, 85.0, 1.0),  # row 2, col 0
            (85.0, 85.0, 1.0),  # row 2, col 2
            (45.0, 45.0, 1.0),  # row 1, col 1
        ]
        cells = tool.region_counts(projected, width, height)
        self.assertEqual(len(cells), 9)
        self.assertEqual(cells, [1, 0, 1, 0, 1, 0, 1, 0, 1])

    def test_edges_land_in_last_row_and_column(self):
        cells = tool.region_counts([(89.0, 89.0, 1.0)], 90, 90)
        self.assertEqual(cells[8], 1)


class BandCountTests(unittest.TestCase):
    def test_boundaries(self):
        depths = [0.3, 0.5, 0.9, 1.0, 2.9, 3.0, 7.9, 8.0]
        bands = tool.band_counts(depths)
        self.assertEqual(
            bands,
            [("<0.5", 1), ("0.5-1", 2), ("1-3", 2), ("3-8", 2), (">=8", 1)],
        )
        self.assertEqual(sum(count for _, count in bands), len(depths))

    def test_empty(self):
        self.assertEqual(sum(count for _, count in tool.band_counts([])), 0)


class FormatStatsTests(unittest.TestCase):
    def stats(self):
        return {
            "seq": 7,
            "elapsed_s": 21.0,
            "width": 640,
            "height": 480,
            "stride": 2,
            "blind": 0.3,
            "scans": 210,
            "images": 630,
            "imus": 4194,
            "scan_hz": 9.98,
            "image_hz": 29.97,
            "imu_hz": 199.7,
            "scan_age_s": 0.041,
            "image_age_s": -0.033,
            "imu_age_s": 0.005,
            "points": 2000,
            "drawn": 812,
            "depth": (0.42, 1.87, 9.1),
            "bands": [("<0.5", 3), ("0.5-1", 10), ("1-3", 990), ("3-8", 600), (">=8", 300)],
            "regions": [0, 10, 5, 120, 300, 80, 40, 200, 57],
            "intrinsics_from": "camera_info",
        }

    def test_reports_counts_rates_ages_bands_and_regions(self):
        text = tool.format_stats(self.stats())
        for needle in (
            "RENDER 7",
            "hz=9.98",
            "hz=29.97",
            "hz=199.7",
            "age=+0.041s",
            "age=-0.033s",
            "camera_info",
            "drawn=812",
            "IN_FOV",
            "bands",
            "regions row0",
            "regions row2",
            "blind=0.30",
        ):
            self.assertIn(needle, text)

    def test_none_rates_print_placeholder(self):
        stats = self.stats()
        stats.update(scan_hz=None, image_hz=None, imu_hz=None, depth=None,
                     regions=[0] * 9, bands=[])
        text = tool.format_stats(stats)
        self.assertIn("n/a", text)

    def test_stale_age_is_flagged(self):
        stats = self.stats()
        stats["image_age_s"] = 3.5
        self.assertIn("STALE", tool.format_stats(stats))


class RenderHtmlTests(unittest.TestCase):
    def test_page_references_both_images_with_cache_buster(self):
        html = tool.render_html(7, 2.0, "stats line")
        self.assertEqual(html.count("?v=7"), 2)
        self.assertIn("latest_frame.png?v=7", html)
        self.assertIn("latest_overlay.png?v=7", html)
        self.assertIn("setTimeout", html)
        self.assertIn("2000", html)
        self.assertIn("stats line", html)

    def test_stats_text_is_escaped(self):
        html = tool.render_html(1, 2.0, "<b>raw</b>")
        self.assertIn("&lt;b&gt;raw&lt;/b&gt;", html)
        self.assertNotIn("<b>raw</b>", html)


if __name__ == "__main__":
    unittest.main()
