#!/usr/bin/env python3
"""Tests for check_replay_configs.py's decision logic.

The checker's logic functions are pure (no ROS imports), so these tests run
anywhere; the end-to-end run against the real bag is the box evidence step
documented in T3.5_CONSUMER_CONTRACT.md.

    cd docs/sherman_docs/tools/fastlivo
    python3 -m unittest -v test_check_replay_configs
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path
from unittest import mock

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

    def test_frozen_identity_matches_the_frozen_constants(self) -> None:
        frozen = checker.FROZEN_T35B_IDENTITY
        self.assertEqual(
            {name: entry["count"] for name, entry in frozen["topics"].items()},
            {name: spec[1] for name, spec in checker.EXPECTED_TOPICS.items()},
        )
        self.assertEqual(frozen["duration_ns"], checker.EXPECTED_DURATION_NS)
        self.assertEqual(frozen["message_count"], checker.EXPECTED_MESSAGE_COUNT)


class TestBagIdentitySnapshot(unittest.TestCase):
    """The new-bag path: a reviewed snapshot replaces the frozen t35b constants."""

    COUNTS = {
        checker.LIDAR: 900,
        checker.IMU: 18000,
        checker.IMAGE: 2700,
        checker.CAMINFO: 2700,
    }
    TYPES = {
        checker.LIDAR: "livox_ros_driver2/msg/CustomMsg",
        checker.IMU: "sensor_msgs/msg/Imu",
        checker.IMAGE: "sensor_msgs/msg/Image",
        checker.CAMINFO: "sensor_msgs/msg/CameraInfo",
    }
    DURATION_NS = 75_000_000_000
    MESSAGE_COUNT = 24_300

    def _snapshot(self) -> dict:
        return checker.identity_from_bag(self.COUNTS, self.TYPES, self.DURATION_NS, self.MESSAGE_COUNT)

    def test_identity_from_bag_is_canonical(self) -> None:
        identity = self._snapshot()
        self.assertEqual(set(identity), {"schema", "topics", "duration_ns", "message_count"})
        self.assertEqual(identity["schema"], checker.IDENTITY_SCHEMA)
        self.assertEqual(identity["duration_ns"], self.DURATION_NS)
        self.assertEqual(identity["message_count"], self.MESSAGE_COUNT)
        self.assertEqual(
            identity["topics"][checker.LIDAR],
            {"type": "livox_ros_driver2/msg/CustomMsg", "count": 900},
        )
        self.assertEqual(list(identity["topics"]), sorted(identity["topics"]))

    def test_snapshot_matches_the_bag_it_was_made_from(self) -> None:
        failures, _ = checker.check_bag_identity(
            self.COUNTS, self.TYPES, self.DURATION_NS, self.MESSAGE_COUNT, expected=self._snapshot()
        )
        self.assertEqual(failures, [])

    def test_snapshot_count_drift_names_topic_and_both_numbers(self) -> None:
        counts = dict(self.COUNTS)
        counts[checker.LIDAR] += 3
        failures, _ = checker.check_bag_identity(
            counts, self.TYPES, self.DURATION_NS, self.MESSAGE_COUNT, expected=self._snapshot()
        )
        self.assertEqual(len(failures), 1)
        self.assertIn(checker.LIDAR, failures[0])
        self.assertIn("900", failures[0])
        self.assertIn("903", failures[0])

    def test_snapshot_extra_topic_fails(self) -> None:
        counts = dict(self.COUNTS)
        types = dict(self.TYPES)
        counts["/rosout"] = 12
        types["/rosout"] = "rcl_interfaces/msg/Log"
        failures, _ = checker.check_bag_identity(
            counts, types, self.DURATION_NS, self.MESSAGE_COUNT, expected=self._snapshot()
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("unexpected topic /rosout", failures[0])

    def test_snapshot_missing_topic_fails(self) -> None:
        counts = dict(self.COUNTS)
        types = dict(self.TYPES)
        del counts[checker.CAMINFO]
        del types[checker.CAMINFO]
        failures, _ = checker.check_bag_identity(
            counts, types, self.DURATION_NS, self.MESSAGE_COUNT, expected=self._snapshot()
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("missing expected topic", failures[0])

    def test_snapshot_type_drift_fails(self) -> None:
        types = dict(self.TYPES)
        types[checker.LIDAR] = "sensor_msgs/msg/PointCloud2"
        failures, _ = checker.check_bag_identity(
            self.COUNTS, types, self.DURATION_NS, self.MESSAGE_COUNT, expected=self._snapshot()
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("CustomMsg", failures[0])

    def test_snapshot_duration_drift_fails(self) -> None:
        failures, _ = checker.check_bag_identity(
            self.COUNTS, self.TYPES, self.DURATION_NS + 1, self.MESSAGE_COUNT, expected=self._snapshot()
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("duration", failures[0])

    def test_snapshot_message_count_drift_fails(self) -> None:
        failures, _ = checker.check_bag_identity(
            self.COUNTS, self.TYPES, self.DURATION_NS, self.MESSAGE_COUNT - 1, expected=self._snapshot()
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("message_count", failures[0])

    def test_snapshot_note_says_it_was_declared_not_frozen(self) -> None:
        _, notes = checker.check_bag_identity(
            self.COUNTS, self.TYPES, self.DURATION_NS, self.MESSAGE_COUNT, expected=self._snapshot()
        )
        self.assertTrue(any("declared snapshot" in note for note in notes), notes)


class TestIdentitySnapshotFile(unittest.TestCase):
    BAG_NAME = "t35c_capture_20261019"

    def _identity(self) -> dict:
        identity = checker.identity_from_bag(
            TestBagIdentitySnapshot.COUNTS,
            TestBagIdentitySnapshot.TYPES,
            TestBagIdentitySnapshot.DURATION_NS,
            TestBagIdentitySnapshot.MESSAGE_COUNT,
        )
        identity["bag"] = self.BAG_NAME
        return identity

    def test_render_is_sorted_json_with_trailing_newline(self) -> None:
        identity = self._identity()
        text = checker.render_identity(identity)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(json.loads(text), identity)
        self.assertLess(text.index("duration_ns"), text.index("topics"))

    def test_write_then_load_round_trips(self) -> None:
        identity = self._identity()
        path = Path(self._tmp()) / "identity.json"
        checker.write_identity(path, identity)
        self.assertEqual(checker.load_identity(path), identity)

    def _tmp(self) -> str:
        import tempfile

        return tempfile.mkdtemp(prefix="fastlivo-identity-")

    def test_write_refuses_to_overwrite_an_existing_snapshot(self) -> None:
        path = Path(self._tmp()) / "identity.json"
        path.write_text(checker.render_identity(self._identity()))
        with self.assertRaises(FileExistsError):
            checker.write_identity(path, self._identity())
        self.assertEqual(checker.load_identity(path), self._identity())

    def test_write_with_force_replaces_it(self) -> None:
        path = Path(self._tmp()) / "identity.json"
        path.write_text("{}\n")
        checker.write_identity(path, self._identity(), force=True)
        self.assertEqual(checker.load_identity(path), self._identity())

    def test_load_rejects_bad_shapes(self) -> None:
        good = self._identity()
        cases = {
            "not json": "{",
            "not an object": "[1, 2]",
            "unknown top-level key": json.dumps({**good, "topcis": {}}),
            "schema missing": json.dumps({key: value for key, value in good.items() if key != "schema"}),
            "wrong schema": json.dumps({**good, "schema": checker.IDENTITY_SCHEMA + 1}),
            "topics missing": json.dumps({key: value for key, value in good.items() if key != "topics"}),
            "topics empty": json.dumps({**good, "topics": {}}),
            "topic entry missing count": json.dumps(
                {**good, "topics": {checker.LIDAR: {"type": "livox_ros_driver2/msg/CustomMsg"}}}
            ),
            "topic count is a string": json.dumps(
                {**good, "topics": {checker.LIDAR: {"type": "livox_ros_driver2/msg/CustomMsg", "count": "900"}}}
            ),
            "topic count negative": json.dumps(
                {**good, "topics": {checker.LIDAR: {"type": "livox_ros_driver2/msg/CustomMsg", "count": -1}}}
            ),
            "topic type empty": json.dumps({**good, "topics": {checker.LIDAR: {"type": "", "count": 900}}}),
            "duration float": json.dumps({**good, "duration_ns": 1.5}),
            "message_count zero": json.dumps({**good, "message_count": 0}),
        }
        for label, text in cases.items():
            with self.subTest(label):
                path = Path(self._tmp()) / f"{label.replace(' ', '_')}.json"
                path.write_text(text)
                with self.assertRaises(ValueError):
                    checker.load_identity(path)

    def test_blank_text_cannot_be_parsed_as_an_identity(self) -> None:
        import tempfile

        path = Path(tempfile.mkdtemp(prefix="fastlivo-identity-")) / "blank.json"
        path.write_text("")
        with self.assertRaises(ValueError):
            checker.load_identity(path)


class TestCheckerCliGuards(unittest.TestCase):
    def _main(self, argv: list[str]) -> tuple[int, str]:
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with mock.patch.object(sys, "argv", ["check_replay_configs.py", *argv]), redirect_stdout(buffer):
            code = checker.main()
        return code, buffer.getvalue()

    def test_configs_are_required_without_emit_mode(self) -> None:
        import tempfile

        bag = tempfile.mkdtemp(prefix="fastlivo-bag-")
        code, output = self._main(["--bag-dir", bag])
        self.assertEqual(code, 2)
        self.assertIn("--lio", output)
        self.assertIn("--camera", output)

    def test_emit_and_identity_are_mutually_exclusive(self) -> None:
        import tempfile

        bag = tempfile.mkdtemp(prefix="fastlivo-bag-")
        code, output = self._main(
            ["--bag-dir", bag, "--emit-identity", f"{bag}/out.json", "--identity", f"{bag}/in.json"]
        )
        self.assertEqual(code, 2)
        self.assertIn("mutually exclusive", output)


class TestBlindIsInert(unittest.TestCase):
    """preprocess.blind is carried but the pinned port never sets its threshold."""

    def test_present_blind_produces_one_note(self) -> None:
        notes = checker.check_blind_is_inert({"preprocess.blind": 0.1})
        self.assertEqual(len(notes), 1)

    def test_note_names_the_unassigned_threshold_and_the_finding(self) -> None:
        (note,) = checker.check_blind_is_inert({"preprocess.blind": 0.1})
        self.assertIn("blind_sqr", note)
        self.assertIn("F2", note)
        self.assertIn("T3.5_CONFIG_SWEEP_20261019.md", note)

    def test_absent_blind_produces_no_note(self) -> None:
        self.assertEqual(checker.check_blind_is_inert({"preprocess.voxel_size": 0.5}), [])


class TestCheckerIdentityFlow(unittest.TestCase):
    """main()'s identity wiring. read_bag is stubbed: the Mac has no ROS."""

    BAG_DIR = "/bags/t35c_capture_20261019"

    def _bag(self) -> dict:
        return {
            "counts": dict(TestBagIdentitySnapshot.COUNTS),
            "meta_types": dict(TestBagIdentitySnapshot.TYPES),
            "duration_ns": TestBagIdentitySnapshot.DURATION_NS,
            "message_count": TestBagIdentitySnapshot.MESSAGE_COUNT,
            "topics": dict(TestBagIdentitySnapshot.TYPES),
            "caminfo": {
                "width": 640,
                "height": 480,
                "model": "Pinhole",
                "frame": "camera_color_optical_frame",
                "k": [385.0851135253906, 0.0, 320.0, 0.0, 385.0851135253906, 240.0, 0.0, 0.0, 1.0],
                "d": [0.0] * 5,
            },
            "image": {
                "width": 640,
                "height": 480,
                "encoding": "rgb8",
                "step": 1920,
                "frame": "camera_color_optical_frame",
            },
            "scan": {
                "scans": 2,
                "points": 10,
                "min_line": 0,
                "max_line": 3,
                "min_offset_ns": 0,
                "max_offset_ns": 100_000_000,
            },
        }

    def _run(
        self, argv: list[str], stub_configs: bool = False, lio_stub: dict | None = None
    ) -> tuple[int, str, mock.Mock]:
        import io
        from contextlib import ExitStack, redirect_stdout

        buffer = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, "argv", ["check_replay_configs.py", *argv]))
            read_bag = stack.enter_context(
                mock.patch.object(checker, "read_bag", return_value=self._bag())
            )
            if stub_configs:
                stack.enter_context(
                    mock.patch.object(
                        checker,
                        "yaml_section",
                        side_effect=lambda path, root: dict(lio_stub or {})
                        if root == "laserMapping"
                        else {},
                    )
                )
            stack.enter_context(redirect_stdout(buffer))
            code = checker.main()
        return code, buffer.getvalue(), read_bag

    def test_emit_writes_a_candidate_snapshot_and_checks_nothing(self) -> None:
        import tempfile

        out = Path(tempfile.mkdtemp(prefix="fastlivo-emit-")) / "identity.json"
        code, output, _ = self._run(["--bag-dir", self.BAG_DIR, "--emit-identity", str(out)])
        self.assertEqual(code, 0)
        self.assertIn("IDENTITY_EMITTED", output)
        self.assertNotIn("CONFIG_OK", output)
        identity = checker.load_identity(out)
        self.assertEqual(identity["bag"], "t35c_capture_20261019")
        self.assertEqual(identity["topics"][checker.LIDAR]["count"], 900)

    def test_emit_refuses_to_overwrite_a_reviewed_snapshot(self) -> None:
        import tempfile

        out = Path(tempfile.mkdtemp(prefix="fastlivo-emit-")) / "identity.json"
        existing = {"schema": checker.IDENTITY_SCHEMA, "topics": {"keep": {"type": "t", "count": 1}}}
        out.write_text(checker.render_identity(existing))
        code, output, _ = self._run(["--bag-dir", self.BAG_DIR, "--emit-identity", str(out)])
        self.assertEqual(code, 2)
        self.assertIn("exists", output)
        self.assertEqual(out.read_text(), checker.render_identity(existing))

    def test_unreadable_snapshot_fails_before_the_bag_or_the_configs(self) -> None:
        import tempfile

        bad = Path(tempfile.mkdtemp(prefix="fastlivo-bad-")) / "identity.json"
        bad.write_text("{")
        code, output, read_bag = self._run(
            ["--bag-dir", self.BAG_DIR, "--identity", str(bad), "--lio", "l.yaml", "--camera", "c.yaml"]
        )
        self.assertEqual(code, 1)
        self.assertIn("not JSON", output)
        read_bag.assert_not_called()

    def test_identity_source_is_reported_exactly_once(self) -> None:
        """Both branches print one IDENTITY line: a duplicated block must fail here."""
        import tempfile

        workdir = Path(tempfile.mkdtemp(prefix="fastlivo-once-"))
        lio, camera = workdir / "l.yaml", workdir / "c.yaml"
        for config in (lio, camera):
            config.write_text("# content is irrelevant: yaml_section is stubbed\n")
        snapshot = workdir / "identity.json"
        checker.write_identity(
            snapshot,
            checker.identity_from_bag(
                TestBagIdentitySnapshot.COUNTS,
                TestBagIdentitySnapshot.TYPES,
                TestBagIdentitySnapshot.DURATION_NS,
                TestBagIdentitySnapshot.MESSAGE_COUNT,
            ),
        )
        runs = {
            "frozen": ["--bag-dir", self.BAG_DIR, "--lio", str(lio), "--camera", str(camera)],
            "declared": [
                "--bag-dir",
                self.BAG_DIR,
                "--identity",
                str(snapshot),
                "--lio",
                str(lio),
                "--camera",
                str(camera),
            ],
        }
        for label, argv in runs.items():
            with self.subTest(label):
                _, output, _ = self._run(argv, stub_configs=True)
                self.assertEqual(output.count("IDENTITY source="), 1, output)
                self.assertEqual(output.count("NOTE identity is"), 1, output)

    def test_blind_note_is_reported_once_and_is_not_a_failure(self) -> None:
        import tempfile

        workdir = Path(tempfile.mkdtemp(prefix="fastlivo-blind-"))
        lio, camera = workdir / "l.yaml", workdir / "c.yaml"
        for config in (lio, camera):
            config.write_text("# content is irrelevant: yaml_section is stubbed\n")
        _, output, _ = self._run(
            ["--bag-dir", self.BAG_DIR, "--lio", str(lio), "--camera", str(camera)],
            stub_configs=True,
            lio_stub={"preprocess.blind": 0.1},
        )
        self.assertEqual(output.count("NOTE preprocess.blind"), 1, output)
        self.assertNotIn("FAIL preprocess.blind", output)

    def test_declared_snapshot_drift_fails_naming_the_numbers(self) -> None:
        import tempfile

        workdir = Path(tempfile.mkdtemp(prefix="fastlivo-drift-"))
        path = workdir / "identity.json"
        identity = checker.identity_from_bag(
            TestBagIdentitySnapshot.COUNTS,
            TestBagIdentitySnapshot.TYPES,
            TestBagIdentitySnapshot.DURATION_NS,
            TestBagIdentitySnapshot.MESSAGE_COUNT,
        )
        identity["topics"][checker.LIDAR]["count"] += 1
        checker.write_identity(path, identity)
        lio = workdir / "pair_lio.yaml"
        camera = workdir / "pair_camera.yaml"
        for config in (lio, camera):
            config.write_text("# content is irrelevant: yaml_section is stubbed\n")
        code, output, _ = self._run(
            [
                "--bag-dir",
                self.BAG_DIR,
                "--identity",
                str(path),
                "--lio",
                str(lio),
                "--camera",
                str(camera),
            ],
            stub_configs=True,
        )
        self.assertEqual(code, 1)
        self.assertIn(f"{checker.LIDAR} count 900 != expected 901", output)
        self.assertIn("declared snapshot", output)


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
