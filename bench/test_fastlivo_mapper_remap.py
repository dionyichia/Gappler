"""The live mapper container must keep the mapper's own /tf off the shared tree (stdlib, static).

FAST-LIVO2 always broadcasts camera_init -> aft_mapped on /tf (LIVMapper.cpp:1574, no switch). With odom_source:=fastlivo the
bridge owns odom -> robot_base_link, so that extra tree must go to /fastlivo/tf. The probe script from T3.5d is frozen evidence
(its hash is recorded) and ran in a private domain, so it is exempt; every other live script that starts fastlivo_mapping must remap.
"""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
LIVE = REPO / "docs/sherman_docs/tools/fastlivo/live"
FROZEN = {"t35d_probe_container.sh"}
REMAPS = ("-r /tf:=/fastlivo/tf", "-r /tf_static:=/fastlivo/tf_static")


def mapper_command(text):
    """The fastlivo_mapping ros2 command as one logical line (backslash continuations joined)."""
    joined = re.sub(r"\\\n\s*", " ", text)
    return next(line for line in joined.splitlines() if "fastlivo_mapping" in line and "--ros-args" in line)


class MapperRemapTests(unittest.TestCase):
    def test_the_live_mapper_script_exists_and_remaps_both_tf_topics(self):
        script = LIVE / "t35e_mapper_container.sh"
        self.assertTrue(script.is_file())
        command = mapper_command(script.read_text())
        for remap in REMAPS:
            self.assertIn(remap, command)

    def test_every_non_frozen_live_script_that_starts_the_mapper_remaps(self):
        checked = []
        for script in sorted(LIVE.glob("*.sh")):
            text = script.read_text()
            if "fastlivo_mapping" not in text or script.name in FROZEN:
                continue
            checked.append(script.name)
            for remap in REMAPS:
                self.assertIn(remap, mapper_command(text), script.name)
        self.assertIn("t35e_mapper_container.sh", checked)

    def test_the_frozen_probe_is_unchanged_evidence(self):
        text = (LIVE / "t35d_probe_container.sh").read_text()
        self.assertNotIn("/fastlivo/tf", text, "the T3.5d probe script is recorded by hash and must not be edited")

    def test_the_new_script_keeps_the_safety_limits_of_the_probe(self):
        text = (LIVE / "t35e_mapper_container.sh").read_text()
        for needle in ("--cap-drop ALL", "no-new-privileges:true", "--user \"$(id -u):$(id -g)\"", "--memory 8g", "--pids-limit 512", "ROS_LOCALHOST_ONLY=1"):
            self.assertIn(needle, text)
        self.assertIn("ROS_DOMAIN_ID=${T35_ROS_DOMAIN_ID:-174}", text, "isolated domain 174 unless the operator chooses another")
        self.assertNotIn("--gpus", text)
        self.assertNotIn("--device", text)
        self.assertNotIn("docker.sock", text)


if __name__ == "__main__":
    unittest.main()
