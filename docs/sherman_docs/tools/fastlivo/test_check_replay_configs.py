#!/usr/bin/env python3
"""Tests for check_replay_configs.py's decision logic.

The checker's logic functions are pure (no ROS imports), so these tests run
anywhere; the end-to-end run against the real bag is the box evidence step
documented in T3.5_CONSUMER_CONTRACT.md.

    cd docs/sherman_docs/tools/fastlivo
    python3 -m unittest -v test_check_replay_configs
"""
from __future__ import annotations

import math
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


class TestCameraExtrinsics(unittest.TestCase):
    """Nominal camera-extrinsic composition and the mode-aware checker."""

    @staticmethod
    def _rpy_to_matrix(roll: float, pitch: float, yaw: float) -> tuple[tuple[float, ...], ...]:
        """R = Rz(yaw) @ Ry(pitch) @ Rx(roll): ROS fixed-axis rpy convention."""
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy_, sy = math.cos(yaw), math.sin(yaw)
        return (
            (cy_ * cp, cy_ * sp * sr - sy * cr, cy_ * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy_ * cr, sy * sp * cr - cy_ * sr),
            (-sp, cp * sr, cp * cr),
        )

    def _compose_full_nominal_chain(self) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Recompute Rcl/Pcl from the documented chain inputs, not the constants."""
        # T_base<-livox: M2 retained mount, eye-estimated zero rotation.
        livox = (0.18, 0.0, 0.2)
        # T_base<-colour frame: T5.4 as-fitted chain (screw + Intel body + colour y).
        screw = (0.208, 0.0, 0.528)
        body = (0.01115, 0.0475, 0.0145)
        colour = (screw[0] + body[0], screw[1] + body[1] - 0.059, screw[2] + body[2])
        # Optical axes: fixed rpy(-pi/2, 0, -pi/2) off the colour frame.
        rot = self._rpy_to_matrix(-math.pi / 2, 0.0, -math.pi / 2)
        rot_t = tuple(tuple(rot[j][i] for j in range(3)) for i in range(3))
        delta = tuple(livox[i] - colour[i] for i in range(3))
        rcl = tuple(rot_t[i][j] for i in range(3) for j in range(3))
        pcl = tuple(sum(rot_t[i][k] * delta[k] for k in range(3)) for i in range(3))
        return rcl, pcl

    def _section(self, img_en: object, rcl: object, pcl: object) -> dict:
        return {"common.img_en": img_en, "extrin_calib.Rcl": rcl, "extrin_calib.Pcl": pcl}

    def test_full_chain_reproduces_reviewed_nominal(self) -> None:
        rcl, pcl = self._compose_full_nominal_chain()
        for got, want in zip(rcl, checker.NOMINAL_RCL):
            self.assertAlmostEqual(got, want, places=12)
        for got, want in zip(pcl, checker.NOMINAL_PCL):
            self.assertAlmostEqual(got, want, places=12)

    def test_visual_mode_accepts_reviewed_nominal(self) -> None:
        mode, failures = checker.check_mode(
            self._section(1, list(checker.NOMINAL_RCL), list(checker.NOMINAL_PCL))
        )
        self.assertEqual((mode, failures), ("visual", []))

    def test_visual_mode_rejects_fork_placeholder(self) -> None:
        mode, failures = checker.check_mode(
            self._section(
                1,
                [-0.99592574, 0.01558709, 0.08881982, -0.07711178, -0.65783989,
                 -0.74919988, 0.04675138, -0.75299650, 0.65636163],
                [-0.19803049, 0.12062488, 0.22892291],
            )
        )
        self.assertEqual(mode, "visual")
        self.assertEqual(len(failures), 2)  # one first-mismatch per vector
        self.assertTrue(all("!= reviewed nominal" in f for f in failures))

    def test_visual_mode_rejects_truncated_pcl(self) -> None:
        pcl = list(checker.NOMINAL_PCL)
        pcl[1] = 0.342  # truncated 0.3425
        mode, failures = checker.check_mode(self._section(1, list(checker.NOMINAL_RCL), pcl))
        self.assertEqual(mode, "visual")
        self.assertEqual(len(failures), 1)
        self.assertIn("extrin_calib.Pcl[1]", failures[0])

    def test_diagnostic_mode_accepts_nonempty_placeholder(self) -> None:
        mode, failures = checker.check_mode(self._section(0, [-1.0] * 9, [0.0, 0.0, 0.0]))
        self.assertEqual((mode, failures), ("diagnostic", []))

    def test_diagnostic_mode_rejects_empty_extrinsics(self) -> None:
        mode, failures = checker.check_mode(self._section(0, [], []))
        self.assertEqual(mode, "diagnostic")
        self.assertEqual(len(failures), 2)

    def test_invalid_img_en_fails(self) -> None:
        for bad in (2, None, True, "1"):
            with self.subTest(bad=bad):
                mode, failures = checker.check_mode(
                    self._section(bad, list(checker.NOMINAL_RCL), list(checker.NOMINAL_PCL))
                )
                self.assertIsNone(mode)
                self.assertEqual(len(failures), 1)


class TestLidarImuExtrinsic(unittest.TestCase):
    """LiDAR->IMU extrinsic: the fork's Mid-360 sign defect and its retention."""

    @staticmethod
    def _section(extrinsic_t: object, extrinsic_r: object) -> dict:
        return {"extrin_calib.extrinsic_T": extrinsic_t, "extrin_calib.extrinsic_R": extrinsic_r}

    def test_corrected_value_passes(self) -> None:
        failures, notes = checker.check_lidar_imu_extrinsic(
            self._section(list(checker.NOMINAL_LIDAR_IMU_T), list(checker.LIDAR_IMU_R)),
            retained=False,
        )
        self.assertEqual((failures, notes), ([], []))

    def test_fork_mid360_sign_fails(self) -> None:
        """The pinned fork's staged value is the manual's position, unnegated."""
        failures, notes = checker.check_lidar_imu_extrinsic(
            self._section([0.011, 0.02329, -0.04412], list(checker.LIDAR_IMU_R)), retained=False
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("extrin_calib.extrinsic_T[0]", failures[0])
        self.assertEqual(notes, [])

    def test_rotated_extrinsic_r_fails(self) -> None:
        rot = list(checker.LIDAR_IMU_R)
        rot[1] = 0.1
        failures, _ = checker.check_lidar_imu_extrinsic(
            self._section(list(checker.NOMINAL_LIDAR_IMU_T), rot), retained=False
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("extrin_calib.extrinsic_R[1]", failures[0])

    def test_empty_vectors_fail_per_key(self) -> None:
        failures, _ = checker.check_lidar_imu_extrinsic(self._section([], []), retained=False)
        self.assertEqual(len(failures), 2)

    def test_retained_precorrection_pair_notes_instead_of_failing(self) -> None:
        failures, notes = checker.check_lidar_imu_extrinsic(
            self._section([0.011, 0.02329, -0.04412], list(checker.LIDAR_IMU_R)), retained=True
        )
        self.assertEqual(failures, [])
        self.assertEqual(len(notes), 1)
        self.assertIn("pre-correction", notes[0])
        self.assertIn("T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md", notes[0])

    def test_retained_pair_already_corrected_is_silent(self) -> None:
        failures, notes = checker.check_lidar_imu_extrinsic(
            self._section(list(checker.NOMINAL_LIDAR_IMU_T), list(checker.LIDAR_IMU_R)), retained=True
        )
        self.assertEqual((failures, notes), ([], []))

    def test_nominal_is_the_negation_of_the_manual_imu_position(self) -> None:
        """Mid-360 manual p.15: the IMU chip sits at (+11.0, +23.29, -44.12) mm in the
        point-cloud frame; the code applies extrinsic_T verbatim, so it needs the negation."""
        manual_position_mm = (11.0, 23.29, -44.12)
        for got, want_mm in zip(checker.NOMINAL_LIDAR_IMU_T, manual_position_mm):
            self.assertAlmostEqual(got, -want_mm / 1000.0, places=12)


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

    def test_staged_visual_pair_is_visual_mode(self) -> None:
        section = checker.yaml_section(self.CONFIG / "t35b_proof3_visual.yaml", "laserMapping")
        mode, failures = checker.check_mode(section)
        self.assertEqual((mode, failures), ("visual", []))
        for key in (
            "time_offset.img_time_offset",
            "time_offset.imu_time_offset",
            "time_offset.lidar_time_offset",
        ):
            self.assertEqual(section[key], 0.0)

    def test_visual_pair_equals_diagnostic_except_declared_delta(self) -> None:
        """The visual file may differ from the diagnostic only in mode + Rcl/Pcl."""
        diagnostic = checker.yaml_section(self.CONFIG / "t35b_proof3_lio.yaml", "laserMapping")
        visual = checker.yaml_section(self.CONFIG / "t35b_proof3_visual.yaml", "laserMapping")
        for key in ("common.img_en", "extrin_calib.Rcl", "extrin_calib.Pcl"):
            diagnostic.pop(key, None)
            visual.pop(key, None)
        self.assertEqual(diagnostic, visual)

    def test_staged_pairs_are_the_retained_precorrection_list(self) -> None:
        """Both staged files predate the LiDAR->IMU defect fix and stay byte-unchanged:
        the checker notes their known sign instead of failing them."""
        for name in ("t35b_proof3_lio.yaml", "t35b_proof3_visual.yaml"):
            with self.subTest(name=name):
                self.assertIn(name, checker.PRECORRECTION_PAIRS)
                section = checker.yaml_section(self.CONFIG / name, "laserMapping")
                failures, notes = checker.check_lidar_imu_extrinsic(
                    section, retained=name in checker.PRECORRECTION_PAIRS
                )
                self.assertEqual(failures, [])
                self.assertEqual(len(notes), 1)


if __name__ == "__main__":
    unittest.main()
