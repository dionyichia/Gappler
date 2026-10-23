"""fastlivo mode maps with SLAM Toolbox's scan matching and loop closing off (stdlib, static).

T3.5e diagnostics: scan matching and loop closure warp the 2D map by up to 0.5 m against FAST-LIVO2's own cloud (map A: 76% of cells
within 0.20 m of the PCD), while a map built from the FAST-LIVO2 poses alone agrees (D1: 94%) and reloads about 3 times closer to the
tape. So the fastlivo yaml is D1. wheel mode must stay exactly what it was.
"""
import ast
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "nav/robot_slam/config"
MAPPING = REPO / "nav/robot_slam/launch/slam_mapping.launch.py"
LOCALIZATION = REPO / "nav/robot_slam/launch/slam_localization.launch.py"
D1_KEYS = {"use_scan_matching": "false", "do_loop_closing": "false"}


def keys(path):
    """Flat key -> value of a ROS parameter file (one level under ros__parameters), stdlib."""
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^\s{4}([A-Za-z_]+):\s*([^#\n]*?)\s*(?:#.*)?$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


class SlamConfigTests(unittest.TestCase):
    def test_fastlivo_yaml_turns_scan_matching_and_loop_closing_off(self):
        values = keys(CONFIG / "slam_toolbox_fastlivo.yaml")
        for key, want in D1_KEYS.items():
            self.assertEqual(values[key], want, key)

    def test_it_differs_from_the_wheel_yaml_only_in_those_keys(self):
        wheel, fastlivo = keys(CONFIG / "slam_toolbox.yaml"), keys(CONFIG / "slam_toolbox_fastlivo.yaml")
        changed = {k for k in set(wheel) | set(fastlivo) if wheel.get(k) != fastlivo.get(k)}
        self.assertEqual(changed, set(D1_KEYS), "fastlivo yaml drifted from the wheel yaml: %s" % sorted(changed))

    def test_the_wheel_yaml_is_unchanged_in_meaning(self):
        wheel = keys(CONFIG / "slam_toolbox.yaml")
        self.assertEqual(wheel["do_loop_closing"], "true")
        self.assertNotIn("use_scan_matching", wheel, "the default (on) stays for wheel mode")
        self.assertEqual(wheel["mode"], "mapping")

    def test_the_mapping_launch_picks_the_fastlivo_yaml_only_when_odom_source_is_fastlivo(self):
        tree = ast.parse(MAPPING.read_text())
        assign = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "slam_params_file" for t in n.targets))
        text = ast.unparse(assign)
        self.assertIn("slam_toolbox_fastlivo.yaml", text)
        self.assertIn("slam_toolbox.yaml", text)
        self.assertIn("odom_is_fastlivo", text)
        # exactly: [..., "<dir>/slam_toolbox_fastlivo.yaml' if ", odom_is_fastlivo, " else '", dir, "/slam_toolbox.yaml'"]
        elts = assign.args[0].elts
        i = next(k for k, e in enumerate(elts) if isinstance(e, ast.Constant) and str(e.value).endswith("/slam_toolbox_fastlivo.yaml' if "))
        self.assertIsInstance(elts[i + 1], ast.Name)
        self.assertEqual(elts[i + 1].id, "odom_is_fastlivo")
        self.assertEqual(elts[i + 2].value, " else '")
        self.assertTrue(str(elts[-1].value).endswith("/slam_toolbox.yaml'"))
        node = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "slam_toolbox" for t in n.targets))
        params = next(k.value for k in node.keywords if k.arg == "parameters")
        self.assertEqual([e.id for e in params.elts], ["slam_params_file"])
        self.assertEqual(MAPPING.read_text().count("slam_toolbox_fastlivo.yaml"), 1, "named once")

    def test_localization_is_unchanged(self):
        self.assertNotIn("slam_toolbox_fastlivo", LOCALIZATION.read_text())
        self.assertIn("slam_toolbox_localization.yaml", LOCALIZATION.read_text())


if __name__ == "__main__":
    unittest.main()
