"""The T3.5f live runbook must be copy-pasteable end to end (stdlib, static).

Every command is written out (no ellipses or placeholders), every bash block parses, every file it names exists in the repo or is something the
stage script puts on the box, every check says what to expect and what to do if not, and the floor-mark step is there.
"""
from pathlib import Path
import re
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[1]
RUNBOOK = REPO / "docs/sherman_docs/t3.5f/T3.5f_LIVE_RUNBOOK_20261020.md"
LIVE = REPO / "docs/sherman_docs/tools/fastlivo/live"
TEXT = RUNBOOK.read_text()
BLOCKS = re.findall(r"```bash\n(.*?)```", TEXT, re.S)


class RunbookTests(unittest.TestCase):
    def test_there_are_commands(self):
        self.assertGreater(len(BLOCKS), 20)

    def test_no_ellipsis_or_placeholder_in_any_command_block(self):
        for block in BLOCKS:
            for line in block.splitlines():
                self.assertNotIn("...", line, line)
                self.assertNotRegex(line, r"<[A-Za-z_ -]+>", "placeholder in: " + line)
                self.assertNotIn("TODO", line)
        self.assertNotRegex(TEXT, r"\.\.\. ", "an ellipsis stands in for a command somewhere")

    def test_every_bash_block_parses(self):
        for block in BLOCKS:
            result = subprocess.run(["bash", "-n"], input=block, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, "%s\n%s" % (result.stderr, block))

    def test_files_named_in_commands_exist_or_are_staged(self):
        staged = {"t35e_mapper_container.sh", "tf_edge_check.py", "t35e_replay_precheck.sh", "launch_switch_check.py"}
        for name in staged:
            self.assertTrue((LIVE / name).is_file(), name)
        stage_script = (LIVE / "stage_t35f_live.sh").read_text()
        for name in staged:
            self.assertIn(name, stage_script, "the stage script must copy " + name)
        for match in re.findall(r"\$STAGE/([A-Za-z0-9_.-]+)", "\n".join(BLOCKS)):
            self.assertIn(match, staged | {"prefix"}, "command names a file the stage script does not stage: " + match)
        for match in re.findall(r"docs/sherman_docs/tools/fastlivo/live/([A-Za-z0-9_./-]+)", TEXT):
            self.assertTrue((LIVE / match).exists(), match)

    def test_the_launch_lines_use_the_runbook_switches(self):
        commands = "\n".join(BLOCKS)
        self.assertIn("ros2 launch robot_slam slam_mapping.launch.py odom_source:=fastlivo nav2:=false base_driver:=false", commands)
        self.assertIn("ros2 launch robot_slam base_driver_check.launch.py", commands)
        self.assertNotIn("slam_localization.launch.py", commands, "a graph saved in this mode cannot be reloaded by SLAM Toolbox")

    def test_the_mapper_command_is_complete(self):
        command = next(b for b in BLOCKS if "t35e_mapper_container.sh" in b)
        for needle in ("T35_ROS_DOMAIN_ID=174", "T35_USE_SIM_TIME=false", "T35_REPLAY_IMAGE=sha256:ac276ad768d6ca1907b7b407789574a38f9aebe66216f466d656eb301d546183",
                       "T35_MAPPER_CONFIG=t35c_stationary02_20261019_visual.yaml", "T35_CAMERA_CONFIG=t35c_stationary02_20261019_camera.yaml",
                       "T35_PROBE_OUT=$SESSION/mapper"):
            self.assertIn(needle, command)

    def test_each_check_says_what_to_expect_and_what_to_do_if_not(self):
        checks = re.split(r"\n(?=### Check )", TEXT)[1:]
        self.assertGreaterEqual(len(checks), 10)
        for check in checks:
            title = check.splitlines()[0]
            self.assertIn("**Expect**", check, title)
            self.assertIn("**If not**", check, title)
            self.assertIn("```bash", check, title)

    def test_floor_marks_step_asks_for_at_least_three_with_spacing_and_heading_in_the_session_folder(self):
        self.assertRegex(TEXT, r"(?i)at least 3 floor marks")
        for needle in ("floor_marks.txt", "AB_m=", "AC_m=", "BC_m=", "B_heading_deg=", "C_heading_deg=", "$SESSION/floor"):
            self.assertIn(needle, TEXT)

    def test_the_base_driver_is_off_while_pushing_and_started_once_at_the_end(self):
        self.assertIn("base_driver:=false", TEXT)
        self.assertIn("ros2 param get /xnode_vehicle pub_tf", TEXT)
        self.assertIn("Boolean value is: False", TEXT)
        self.assertIn("tf_edge_check.py --seconds 10", TEXT)
        self.assertIn("tf_edge_check.py --seconds 10 --expect-silent", TEXT)

    def test_map_autosave_is_pointed_at_the_session_folder(self):
        self.assertIn("export GAPPLER_MAP_DIR=$SESSION/maps", TEXT)


if __name__ == "__main__":
    unittest.main()
