"""T6.3a config, S2 detection filtering (T6.3c) and S3 anchor gate (T6.5a)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import math
import unittest

import numpy as np

from memory_graph.anchor_gate import AnchorGate, rotation_angle, should_accept
from memory_graph.config import MemoryGraphConfig
from memory_graph.detection_filter import filter_detections
from memory_graph.tests._fixtures import dets, pose, rot_z

CFG = MemoryGraphConfig()
IMG = (480, 640)


class ConfigTest(unittest.TestCase):
    def test_defaults_are_upstream_values(self):
        self.assertEqual(CFG.sim_threshold, 0.6)
        self.assertEqual(CFG.match_radius_m, 0.025)
        self.assertAlmostEqual(CFG.gate_rotation_rad, math.pi / 4)
        self.assertEqual(CFG.association_mode, "greedy")

    def test_override_and_typo(self):
        cfg = MemoryGraphConfig.from_dict({"sim_threshold": 0.7, "bg_classes": ["wall"]})
        self.assertEqual(cfg.sim_threshold, 0.7)
        self.assertEqual(cfg.bg_classes, ("wall",))
        with self.assertRaises(KeyError):
            MemoryGraphConfig.from_dict({"sim_treshold": 0.7})

    def test_rejects_bad_values(self):
        with self.assertRaises(ValueError):
            MemoryGraphConfig(association_mode="hungarian")
        with self.assertRaises(ValueError):
            MemoryGraphConfig(phys_bias=1.5)


class DetectionFilterTest(unittest.TestCase):
    BOXES = [[0, 0, 100, 100], [10, 10, 200, 200], [50, 50, 150, 120],
             [0, 0, 640, 480], [5, 5, 6, 6], [300, 300, 400, 400]]
    CONFS = [0.9, 0.15, 0.15, 0.95, 0.8, 0.5]
    LABELS = ["chair", "cup", "sink", "wall", "chair", "table"]

    def run_filter(self, order):
        d = dets([self.BOXES[i] for i in order], [self.CONFS[i] for i in order],
                 [self.LABELS[i] for i in order])
        return filter_detections(d, IMG, targets={"cup"}, cfg=CFG)

    def test_target_kept_at_low_confidence_non_target_dropped(self):
        out = self.run_filter(range(6))
        self.assertIn("cup", out.label)        # 0.15 target survives
        self.assertNotIn("sink", out.label)    # 0.15 non-target dropped

    def test_background_and_tiny_boxes_dropped(self):
        out = self.run_filter(range(6))
        self.assertNotIn("wall", out.label)
        self.assertEqual(out.label.count("chair"), 1)   # the 1x1 px chair is gone

    def test_sorted_and_input_order_does_not_matter(self):
        reference = self.run_filter(range(6))
        self.assertEqual(reference.label, ["chair", "table", "cup"])
        self.assertTrue(np.all(np.diff(reference.conf) <= 0))
        rng = np.random.default_rng(1)
        for _ in range(20):
            out = self.run_filter(rng.permutation(6))
            self.assertEqual(out.label, reference.label)
            np.testing.assert_array_equal(out.xyxy, reference.xyxy)

    def test_empty_input(self):
        self.assertEqual(len(filter_detections(dets([], [], []), IMG, set(), CFG)), 0)


class AnchorGateTest(unittest.TestCase):
    def test_stationary_camera_accepted_once(self):
        gate = AnchorGate(CFG)
        T = pose()
        self.assertTrue(gate.check(T, ["chair"], set()))
        gate.commit(T)
        for _ in range(5):
            self.assertFalse(gate.check(T, ["chair"], set()))

    def test_move_turn_or_target_accepts_again(self):
        gate = AnchorGate(CFG)
        gate.commit(pose())
        self.assertTrue(gate.check(pose(t=(1.1, 0, 0)), ["chair"], set()))
        self.assertFalse(gate.check(pose(t=(0.9, 0, 0)), ["chair"], set()))
        self.assertTrue(gate.check(pose(rot_z(50)), ["chair"], set()))
        self.assertFalse(gate.check(pose(rot_z(30)), ["chair"], set()))
        self.assertTrue(gate.check(pose(), ["chair", "cup"], {"cup"}))

    def test_no_detections_rejected_even_first(self):
        self.assertFalse(should_accept(pose(), [], None, set(), CFG))

    def test_last_pose_moves_only_on_commit(self):
        gate = AnchorGate(CFG)
        gate.commit(pose())
        moved = pose(t=(2, 0, 0))
        self.assertTrue(gate.check(moved, ["chair"], set()))
        self.assertTrue(gate.check(moved, ["chair"], set()))   # not committed yet
        gate.commit(moved)
        self.assertFalse(gate.check(moved, ["chair"], set()))

    def test_rotation_angle(self):
        self.assertAlmostEqual(rotation_angle(np.eye(3), rot_z(30)), math.radians(30))
        self.assertAlmostEqual(rotation_angle(rot_z(10), rot_z(10)), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
