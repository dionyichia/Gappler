"""Known-room geometry for the isolated SLAM persistence bench; no ROS needed."""
import math
import os
import signal
import subprocess
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / "nodes"))
import test_slam_persistence as persistence
from test_slam_persistence import ray_range, scan_ranges, pose_error, await_startup


class SlamFixtureTests(unittest.TestCase):
    def test_localization_startup_retains_config_and_explicit_seed(self):
        helper = getattr(persistence, "fixture_parameters", None)
        self.assertTrue(callable(helper), "missing isolated startup parameter builder")
        source = {"mode": "localization", "map_start_at_dock": True, "solver_plugin": "solver"}
        result = helper(source, "localization", "/owned snapshot/completed_map", (0.8, 0.6, 0.2))
        self.assertEqual(result["map_file_name"], "/owned snapshot/completed_map")
        self.assertEqual(result["map_start_pose"], [0.8, 0.6, 0.2])
        self.assertFalse(result["map_start_at_dock"])
        self.assertEqual(result["solver_plugin"], "solver")
        self.assertEqual(result["scan_topic"], "/t35_slam/scan")
        self.assertTrue(source["map_start_at_dock"], "input config mutated")

    def test_scan_relocation_can_hold_odometry_continuous(self):
        helper = getattr(persistence, "odometry_pose", None)
        self.assertTrue(callable(helper), "missing independent scan/odometry fixture")
        self.assertEqual(helper((1, 2, 0.3), (0.4, -0.3, 0.1), (0, 0, 0)), (0, 0, 0))
        self.assertEqual(helper((1, 2, 0.3), (0.4, -0.3, 0.1)), (1.4, 1.7, 0.4))

    def test_map_odom_composition_rotates_translation(self):
        helper = getattr(persistence, "compose_pose", None)
        self.assertTrue(callable(helper), "missing independent TF composition check")
        result = helper((1, 2, math.pi / 2), (3, 0, -math.pi / 2))
        for actual, expected in zip(result, (1, 5, 0)):
            self.assertAlmostEqual(actual, expected)

    def test_localization_witness_needs_pose_and_consistent_tf(self):
        helper = getattr(persistence, "localization_matches", None)
        self.assertTrue(callable(helper), "missing pose/TF witness check")
        expected = (1, 2, 0)
        self.assertTrue(helper(expected, (0, 0, 0), expected, expected))
        for pose, transform in ((None, (0, 0, 0)), (expected, None),
                                (expected, (1, 0, 0)), ((float('nan'), 2, 0), (0, 0, 0))):
            self.assertFalse(helper(pose, transform, expected, expected))

    def test_interrupted_startup_stops_owned_child(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)

        def stop(process):
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=3)

        def interrupted():
            raise KeyboardInterrupt

        try:
            with self.assertRaises(KeyboardInterrupt):
                await_startup(child, interrupted, lambda _: None, stop)
            self.assertIsNotNone(child.poll(), "interrupted startup leaked its child")
        finally:
            if child.poll() is None:
                stop(child)

    def test_cardinal_wall_distances_at_origin(self):
        for angle, distance in ((0, 5), (math.pi / 2, 4), (math.pi, 3), (-math.pi / 2, 2)):
            self.assertAlmostEqual(ray_range(0, 0, angle), distance)

    def test_internal_wall_is_nearer_than_outer_wall(self):
        self.assertAlmostEqual(ray_range(0, 1, 0), 2)
        self.assertAlmostEqual(ray_range(0, 0, 0), 5)

    def test_heading_rotates_scan_and_translation_changes_ranges(self):
        self.assertAlmostEqual(scan_ranges((0, 0, math.pi / 2), 4)[0], 4)
        self.assertAlmostEqual(scan_ranges((1, 0, 0), 4)[0], 4)
        self.assertEqual(len(scan_ranges((0, 0, 0))), 720)
        self.assertTrue(all(0.1 < value < 20 for value in scan_ranges((0, 0, 0))))

    def test_pose_error_wraps_heading(self):
        distance, heading = pose_error((1, 2, math.pi - 0.01), (1.3, 2.4, -math.pi + 0.01))
        self.assertAlmostEqual(distance, 0.5)
        self.assertAlmostEqual(heading, 0.02)


if __name__ == "__main__":
    unittest.main()
