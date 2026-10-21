"""The offline acceptance harness must replay only what the real system would see (stdlib, static).

The bags also hold the mapper's own outputs and its TF. Replaying those would put a second source of odom and camera_init on the
bus, so only the mapper pose and the raw LiDAR are played; everything else is derived by the code under test. The PCD is read
straight from the bag file, not played.
"""
import ast
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "docs/sherman_docs/tools/fastlivo/acceptance/option2_offline_acceptance.py"
ALLOWED = ["/aft_mapped_to_init", "/livox/lidar"]


class HarnessPlaybackTests(unittest.TestCase):
    def play_commands(self):
        tree = ast.parse(HARNESS.read_text())
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.List) and any(isinstance(e, ast.Constant) and e.value == "bag" for e in node.elts) and \
                    any(isinstance(e, ast.Constant) and e.value == "play" for e in node.elts):
                found.append(node)
        return found

    def test_the_player_gets_exactly_the_mapper_pose_and_the_raw_lidar(self):
        commands = self.play_commands()
        self.assertEqual(len(commands), 1, "one ros2 bag play command")
        elts = commands[0].elts
        values = [e.value for e in elts if isinstance(e, ast.Constant)]
        topics = values[values.index("--topics") + 1:]
        topics = [t for t in topics if isinstance(t, str) and t.startswith("/")]
        self.assertEqual(topics, ALLOWED)

    def test_no_recorded_tf_or_mapper_output_is_named_in_the_play_command(self):
        text = ast.unparse(self.play_commands()[0])
        for banned in ("/tf", "/tf_static", "/cloud_registered", "/path", "/Laser_map", "/rgb_img", "/cloud_effected"):
            self.assertNotIn("'%s'" % banned, text, banned)

    def test_the_pcd_comes_from_reading_the_bag_file_not_from_playback(self):
        source = HARNESS.read_text()
        self.assertIn("SequentialReader", source)
        self.assertIn('"/cloud_registered"', source.split("def pcd_from_bag")[1].split("\ndef ")[0])

    def test_both_stamp_variants_exist_and_the_default_is_the_recorded_stamps(self):
        source = HARNESS.read_text()
        self.assertIn('choices=("recorded", "scanend")', source)
        self.assertIn('default="recorded"', source)


    def test_the_runner_refuses_to_start_unless_the_box_precheck_is_clear(self):
        runner = (REPO / "docs/sherman_docs/tools/fastlivo/acceptance/run_phase3.sh").read_text()
        gate = runner.index("PRECHECK")
        self.assertIn("|| { echo", runner[gate:gate + 400], "a blocked pre-check must stop the runner")
        self.assertLess(gate, runner.index("\nrun map"), "the gate comes before the first session")
        self.assertIn("exit 1", runner[gate:runner.index("\nrun map")])
        self.assertIn("set +u", runner, "the ROS setup scripts do not tolerate set -u")


    def test_the_diagnostic_runner_is_gated_on_the_precheck_before_and_between_sessions(self):
        runner = (REPO / "docs/sherman_docs/tools/fastlivo/acceptance/diag_runner.sh").read_text()
        gate = runner.index("PRECHECK")
        self.assertIn("|| { echo", runner[gate:gate + 300])
        self.assertLess(gate, runner.index("\nrun map"))
        self.assertIn('bash "$PRECHECK" > /dev/null 2>&1 || { echo "BLOCKED mid-run; stopping"', runner, "re-checked before every session")
        self.assertIn('skip, already done', runner, "a stopped run can be resumed")
        self.assertIn("set +u", runner)

    def test_slam_parameter_overrides_are_recorded_in_the_result(self):
        source = HARNESS.read_text()
        self.assertIn('"slam_params": args.slam_param', source)
        self.assertIn('"-p", kv.replace("=", ":=", 1)', source)


if __name__ == "__main__":
    unittest.main()
