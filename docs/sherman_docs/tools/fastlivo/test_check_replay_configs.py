#!/usr/bin/env python3
"""Tests for check_replay_configs.py's decision logic.

The checker's logic functions are pure (no ROS imports), so these tests run
anywhere; the end-to-end run against the real bag is the box evidence step
documented in T3.5_CONSUMER_CONTRACT.md.

    cd docs/sherman_docs/tools/fastlivo
    python3 -m unittest -v test_check_replay_configs
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_replay_configs as checker  # noqa: E402

try:
    import yaml  # noqa: F401

    HAVE_YAML = True
except ImportError:  # the staged-pair tests need PyYAML; the logic tests do not
    HAVE_YAML = False

CAM_OK = {
    "use_sim_time": True,
    "cam_model": "Pinhole",
    "cam_width": 640,
    "cam_height": 480,
    "scale": 1.0,
    "cam_fx": 385.0851135253906,
    "cam_fy": 384.5696105957031,
    "cam_cx": 324.9161376953125,
    "cam_cy": 248.54244995117188,
    "cam_d0": -0.05590025335550308,
    "cam_d1": 0.06613793224096298,
    "cam_d2": 0.00020105774456169456,
    "cam_d3": 0.0002285563386976719,
    "cam_d4": -0.021481290459632874,
}
CI_OK = {
    "width": 640,
    "height": 480,
    "model": "plumb_bob",
    "frame": "camera_color_optical_frame",
    "k": [
        385.0851135253906, 0.0, 324.9161376953125,
        0.0, 384.5696105957031, 248.54244995117188,
        0.0, 0.0, 1.0,
    ],
    "d": [
        -0.05590025335550308, 0.06613793224096298, 0.00020105774456169456,
        0.0002285563386976719, -0.021481290459632874,
    ],
}
IMAGE_OK = {
    "width": 640,
    "height": 480,
    "encoding": "rgb8",
    "step": 1920,
    "frame": "camera_color_optical_frame",
}


class TestParamKeys(unittest.TestCase):
    def test_unknown_key_fails_inert_and_builtin_pass(self) -> None:
        section = {
            "use_sim_time": True,
            "preprocess.scan_line": 4,
            "imu.b_acc_cov": 0.0001,
            "preprocess.scan_lien": 4,  # typo
        }
        failures, notes = checker.check_param_keys(
            section, checker.DECLARED, checker.KNOWN_INERT_LIO
        )
        self.assertEqual(failures, ["config key the pinned consumer does not declare: preprocess.scan_lien"])
        self.assertEqual(notes, ["inert key carried for documentation: imu.b_acc_cov"])

    def test_vector_typed_declared_keys_accepted(self) -> None:
        """Regression: vector<...> declare_parameter templates must be in DECLARED."""
        section = {
            "extrin_calib.extrinsic_T": [0.0, 0.0, 0.0],
            "extrin_calib.extrinsic_R": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            "extrin_calib.Pcl": [0.0, 0.0, 0.0],
            "extrin_calib.Rcl": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            "lio.layer_init_num": [5, 5, 5, 5, 5],
        }
        failures, notes = checker.check_param_keys(
            section, checker.DECLARED, checker.KNOWN_INERT_LIO
        )
        self.assertEqual(failures, [])
        self.assertEqual(notes, [])

    def test_all_camera_keys_known(self) -> None:
        failures, notes = checker.check_param_keys(
            CAM_OK, checker.CAMERA_DECLARED, checker.KNOWN_INERT_CAMERA
        )
        self.assertEqual(failures, [])
        self.assertEqual(notes, ["inert key carried for documentation: cam_d4"])

    def test_staged_lio_keys_are_declared(self) -> None:
        lio = {
            "use_sim_time": True,
            "common.lid_topic": "/livox/lidar",
            "preprocess.lidar_type": 1,
            "lio.min_iterations": 5,
            "lio.max_iterations": 5,  # would be silently unused
        }
        failures, _ = checker.check_param_keys(lio, checker.DECLARED, checker.KNOWN_INERT_LIO)
        self.assertEqual(failures, ["config key the pinned consumer does not declare: lio.max_iterations"])


class TestRouting(unittest.TestCase):
    def test_custommsg_bag_with_avia_branch(self) -> None:
        self.assertEqual(
            checker.check_routing(1, "livox_ros_driver2", "livox_ros_driver2/msg/CustomMsg"), []
        )

    def test_pointcloud_bag_with_mid360_branch(self) -> None:
        self.assertEqual(
            checker.check_routing(8, "livox_ros_driver2", "sensor_msgs/msg/PointCloud2"), []
        )

    def test_avia_branch_against_pointcloud_bag_fails(self) -> None:
        failures = checker.check_routing(1, "livox_ros_driver2", "sensor_msgs/msg/PointCloud2")
        self.assertEqual(len(failures), 1)
        self.assertIn("CustomMsg", failures[0])

    def test_mid360_branch_against_custommsg_bag_fails(self) -> None:
        failures = checker.check_routing(8, "livox_ros_driver2", "livox_ros_driver2/msg/CustomMsg")
        self.assertEqual(len(failures), 1)
        self.assertIn("PointCloud2", failures[0])

    def test_wrong_package_name_fails(self) -> None:
        failures = checker.check_routing(1, "livox_interfaces", "livox_ros_driver2/msg/CustomMsg")
        self.assertEqual(len(failures), 1)

    def test_unsupported_branch_fails(self) -> None:
        failures = checker.check_routing(2, "livox_ros_driver2", "sensor_msgs/msg/PointCloud2")
        self.assertEqual(len(failures), 1)


class TestScanLine(unittest.TestCase):
    def test_exact_gate_passes(self) -> None:
        self.assertEqual(checker.check_scan_line(3, 4), [])

    def test_line_at_gate_fails(self) -> None:
        failures = checker.check_scan_line(4, 4)
        self.assertEqual(len(failures), 1)
        self.assertIn("silently dropped", failures[0])

    def test_invalid_scan_line_fails(self) -> None:
        self.assertEqual(len(checker.check_scan_line(3, 0)), 1)
        self.assertEqual(len(checker.check_scan_line(3, "4")), 1)

    def test_no_sample_fails(self) -> None:
        self.assertEqual(len(checker.check_scan_line(None, 4)), 1)


class TestOffsetBounds(unittest.TestCase):
    def test_within_budget_passes(self) -> None:
        self.assertEqual(checker.check_offset_bounds(0, 100_470_031), [])

    def test_at_budget_passes(self) -> None:
        self.assertEqual(checker.check_offset_bounds(0, checker.MAX_OFFSET_NS), [])

    def test_over_budget_fails(self) -> None:
        failures = checker.check_offset_bounds(0, checker.MAX_OFFSET_NS + 1)
        self.assertEqual(len(failures), 1)
        self.assertIn("scan budget", failures[0])

    def test_negative_fails(self) -> None:
        self.assertEqual(len(checker.check_offset_bounds(-1, 1_000)), 1)


class TestCamera(unittest.TestCase):
    def test_exact_values_pass(self) -> None:
        failures, notes = checker.check_camera_config(CAM_OK, CI_OK, IMAGE_OK)
        self.assertEqual(failures, [])
        self.assertTrue(any("cam_d4" in note for note in notes))

    def test_truncated_float_fails(self) -> None:
        cam = dict(CAM_OK, cam_fx=385.0851)
        failures, _ = checker.check_camera_config(cam, CI_OK, IMAGE_OK)
        self.assertEqual(len(failures), 1)
        self.assertIn("cam_fx", failures[0])

    def test_missing_cam_d4_fails(self) -> None:
        cam = {k: v for k, v in CAM_OK.items() if k != "cam_d4"}
        failures, _ = checker.check_camera_config(cam, CI_OK, IMAGE_OK)
        self.assertEqual(len(failures), 1)
        self.assertIn("cam_d4 absent", failures[0])

    def test_wrong_cam_d4_fails(self) -> None:
        cam = dict(CAM_OK, cam_d4=0.0)
        failures, _ = checker.check_camera_config(cam, CI_OK, IMAGE_OK)
        self.assertEqual(len(failures), 1)
        self.assertIn("cam_d4", failures[0])

    def test_short_d_vector_fails(self) -> None:
        ci = dict(CI_OK, d=CI_OK["d"][:4])
        failures, _ = checker.check_camera_config(CAM_OK, ci, IMAGE_OK)
        self.assertEqual(len(failures), 1)

    def test_scaled_geometry_mismatch_fails(self) -> None:
        cam = dict(CAM_OK, scale=0.5)
        failures, _ = checker.check_camera_config(cam, CI_OK, IMAGE_OK)
        self.assertEqual(len(failures), 1)
        self.assertIn("resize path", failures[0])

    def test_bgr8_encoding_fails(self) -> None:
        image = dict(IMAGE_OK, encoding="bgr8")
        failures, _ = checker.check_camera_config(CAM_OK, CI_OK, image)
        self.assertEqual(len(failures), 1)
        self.assertIn("rgb8", failures[0])

    def test_int_keys_must_be_ints(self) -> None:
        cam = dict(CAM_OK, cam_width=640.0)
        failures, _ = checker.check_camera_config(cam, CI_OK, IMAGE_OK)
        self.assertGreaterEqual(len(failures), 1)


class TestBagIdentity(unittest.TestCase):
    def _good(self) -> tuple[dict, dict, int, int]:
        counts = {name: spec[1] for name, spec in checker.EXPECTED_TOPICS.items()}
        types = {name: spec[0] for name, spec in checker.EXPECTED_TOPICS.items()}
        return counts, types, checker.EXPECTED_DURATION_NS, checker.EXPECTED_MESSAGE_COUNT

    def test_frozen_identity_passes(self) -> None:
        failures, _ = checker.check_bag_identity(*self._good())
        self.assertEqual(failures, [])

    def test_extra_topic_fails(self) -> None:
        counts, types, duration, message_count = self._good()
        counts["/odom"] = 1
        types["/odom"] = "nav_msgs/msg/Odometry"
        failures, _ = checker.check_bag_identity(counts, types, duration, message_count)
        self.assertEqual(len(failures), 1)
        self.assertIn("unexpected topic", failures[0])

    def test_count_drift_fails(self) -> None:
        counts, types, duration, message_count = self._good()
        counts[checker.LIDAR] += 1
        failures, _ = checker.check_bag_identity(counts, types, duration, message_count)
        self.assertEqual(len(failures), 1)
        self.assertIn("count", failures[0])

    def test_type_drift_fails(self) -> None:
        counts, types, duration, message_count = self._good()
        types[checker.LIDAR] = "sensor_msgs/msg/PointCloud2"
        failures, _ = checker.check_bag_identity(counts, types, duration, message_count)
        self.assertEqual(len(failures), 1)
        self.assertIn("type", failures[0])


@unittest.skipUnless(HAVE_YAML, "PyYAML not available")
class TestStagedPairKeys(unittest.TestCase):
    """The staged repo configs must satisfy the checker's static key checks."""

    CONFIG = HERE / "replay" / "config"

    def test_staged_lio_keys(self) -> None:
        section = checker.yaml_section(self.CONFIG / "t35b_proof3_lio.yaml", "laserMapping")
        failures, _ = checker.check_param_keys(section, checker.DECLARED, checker.KNOWN_INERT_LIO)
        self.assertEqual(failures, [])

    def test_staged_camera_keys_and_types(self) -> None:
        section = checker.yaml_section(self.CONFIG / "t35b_proof3_camera.yaml", "parameter_blackboard")
        failures, _ = checker.check_param_keys(
            section, checker.CAMERA_DECLARED, checker.KNOWN_INERT_CAMERA
        )
        self.assertEqual(failures, [])
        for key in checker.CAMERA_INT_KEYS:
            self.assertIs(type(section[key]), int)

    def test_staged_pair_is_diagnostic_mode(self) -> None:
        section = checker.yaml_section(self.CONFIG / "t35b_proof3_lio.yaml", "laserMapping")
        self.assertEqual(section["common.img_en"], 0)
        for key in (
            "time_offset.img_time_offset",
            "time_offset.imu_time_offset",
            "time_offset.lidar_time_offset",
        ):
            self.assertEqual(section[key], 0.0)


if __name__ == "__main__":
    unittest.main()
