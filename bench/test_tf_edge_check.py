"""The live TF edge checker's verdict logic (stdlib, no ROS).

The base driver creates its /tf publisher even with pub_tf off, so counting publishers would raise a false alarm. The check is by message
rate on the odom edge: with the mapper running, only the bridge may publish it (about 10 Hz); with the mapper stopped, nothing may.
"""
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tf_edge_check", REPO / "docs/sherman_docs/tools/fastlivo/live/tf_edge_check.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)
EDGE = ("odom", "robot_base_link")


class JudgeTests(unittest.TestCase):
    def test_one_bridge_edge_at_the_expected_rate_passes(self):
        ok, lines = chk.judge({EDGE: 104}, 10.0)
        self.assertTrue(ok, lines)

    def test_a_second_publisher_doubles_the_rate_and_fails(self):
        ok, lines = chk.judge({EDGE: 104 + 500}, 10.0)
        self.assertFalse(ok)
        self.assertTrue(any("second publisher" in l or "too high" in l for l in lines))

    def test_a_silent_edge_fails_unless_silence_is_expected(self):
        self.assertFalse(chk.judge({}, 10.0)[0])
        self.assertTrue(chk.judge({}, 10.0, expect_silent=True)[0])
        self.assertFalse(chk.judge({EDGE: 3}, 10.0, expect_silent=True)[0], "any odom edge message while the mapper is stopped")

    def test_the_mapper_tree_on_the_shared_tf_fails(self):
        ok, lines = chk.judge({EDGE: 104, ("camera_init", "aft_mapped"): 200}, 10.0)
        self.assertFalse(ok)
        self.assertTrue(any("camera_init" in l for l in lines))

    def test_other_edges_are_reported_but_not_failed(self):
        ok, lines = chk.judge({EDGE: 104, ("map", "odom"): 500, ("robot_base_link", "livox_frame"): 1}, 10.0)
        self.assertTrue(ok, lines)
        self.assertTrue(any("map -> odom" in l for l in lines))

    def test_a_low_rate_fails(self):
        self.assertFalse(chk.judge({EDGE: 20}, 10.0)[0])


if __name__ == "__main__":
    unittest.main()
