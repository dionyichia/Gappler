"""The pose-half count and the SAM 3 time it saves (T6.5).

Made-up drives, so the tests need no bag. The run on the lab drive is in
docs/bench-runs/2026-10-22-labbox-t6.5-pose-gate-sweep.txt.
"""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.gate_sweep import fixed_rate_keeps, pose_gate_keeps, sweep
from memory_graph.tests._fixtures import pose, rot_z

CFG = MemoryGraphConfig()


def straight_drive(metres, step=0.3):
    """A camera driving along x, one photo every `step` metres, 10 photos a second.
    0.3 m steps keep every distance well away from the 1 m limit."""
    n = int(round(metres / step)) + 1
    return [i * 0.1 for i in range(n)], [pose(t=(i * step, 0, 0)) for i in range(n)]


class PoseGateKeepsTest(unittest.TestCase):
    def test_a_camera_standing_still_is_kept_once(self):
        self.assertEqual(pose_gate_keeps([pose()] * 50, CFG), [0])

    def test_a_straight_drive_keeps_a_photo_past_every_metre(self):
        _, poses = straight_drive(6.0)
        # 0.9 m is short of the limit, so every 4th photo, 1.2 m on, is kept
        self.assertEqual(pose_gate_keeps(poses, CFG), [0, 4, 8, 12, 16, 20])

    def test_turning_on_the_spot_keeps_a_photo_past_every_45_degrees(self):
        poses = [pose(rot_z(d)) for d in range(0, 181, 10)]
        self.assertEqual([10 * i for i in pose_gate_keeps(poses, CFG)], [0, 50, 100, 150])

    def test_the_last_kept_pose_is_the_reference(self):
        """Small steps do not add up unless a photo was kept: the distance is to
        the last kept photo, not to the previous one."""
        poses = [pose(t=(x, 0, 0)) for x in (0, 0.6, 1.2, 1.5, 2.3)]
        self.assertEqual(pose_gate_keeps(poses, CFG), [0, 2, 4])


class FixedRateTest(unittest.TestCase):
    def test_one_photo_a_second(self):
        t = [i * 0.1 for i in range(31)]
        self.assertEqual(fixed_rate_keeps(t, 1.0), [0, 10, 20, 30])

    def test_a_rate_must_be_positive(self):
        with self.assertRaises(ValueError):
            fixed_rate_keeps([0.0], 0)


class SweepTest(unittest.TestCase):
    def test_counts_and_savings(self):
        t, poses = straight_drive(12.0)         # 41 photos over 4 s, kept every 4th
        result = sweep(t, poses, [1.0], [45.0], sam3_seconds=2.0)
        self.assertEqual(result["frames"], 41)
        self.assertEqual(result["duration_s"], 4.0)
        self.assertEqual(result["every_frame"], {"calls": 41, "sam3_seconds": 82.0})
        self.assertEqual(result["fixed_rate"]["calls"], 5)
        (row,) = result["rows"]
        self.assertEqual(row["kept"], 11)
        self.assertEqual(row["per_minute"], 165.0)
        self.assertEqual(row["sam3_seconds"], 22.0)
        self.assertAlmostEqual(row["saved_vs_every_frame"], round(1 - 11 / 41, 4))
        self.assertAlmostEqual(row["saved_vs_fixed_rate"], round(1 - 11 / 5, 4))

    def test_one_row_per_setting_and_a_wider_gate_keeps_fewer(self):
        t, poses = straight_drive(12.0)
        rows = sweep(t, poses, [0.5, 1.0, 2.0], [30.0, 45.0], sam3_seconds=1.0)["rows"]
        self.assertEqual([(r["metres"], r["degrees"]) for r in rows],
                         [(0.5, 30.0), (0.5, 45.0), (1.0, 30.0), (1.0, 45.0), (2.0, 30.0), (2.0, 45.0)])
        kept = [r["kept"] for r in rows if r["degrees"] == 45.0]
        self.assertEqual(kept, sorted(kept, reverse=True))
        self.assertGreater(kept[0], kept[-1])

    def test_the_setting_does_not_change_the_config_it_was_given(self):
        t, poses = straight_drive(3.0)
        cfg = MemoryGraphConfig()
        result = sweep(t, poses, [0.5], [30.0], sam3_seconds=1.0, cfg=cfg)
        self.assertEqual(cfg.gate_translation_m, 1.0)
        self.assertEqual(result["real_gate"], {"metres": 1.0, "degrees": 45.0})

    def test_mismatched_or_empty_input_is_refused(self):
        with self.assertRaises(ValueError):
            sweep([0.0, 1.0], [pose()], [1.0], [45.0], 1.0)
        with self.assertRaises(ValueError):
            sweep([], [], [1.0], [45.0], 1.0)


if __name__ == "__main__":
    unittest.main()
