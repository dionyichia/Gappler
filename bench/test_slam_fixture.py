"""Known-room geometry for the isolated SLAM persistence bench; no ROS needed."""
import math
import os
import signal
import subprocess
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / "nodes"))
from test_slam_persistence import ray_range, scan_ranges, pose_error, await_startup


class SlamFixtureTests(unittest.TestCase):
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
