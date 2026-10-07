"""Map prerequisites must fail before localization constructs hardware actions."""
import ast
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "shared"))
from slam_maps import require_serialized_map


class SlamMapTests(unittest.TestCase):
    def test_requires_both_nonempty_regular_files(self):
        with tempfile.TemporaryDirectory(prefix="map with spaces ") as directory:
            prefix = Path(directory) / "completed_map"
            for suffix in (".posegraph", ".data"):
                with self.assertRaisesRegex(ValueError, "serialized map"):
                    require_serialized_map(prefix)
                Path(str(prefix) + suffix).write_bytes(b"fixture; not a real graph")
            self.assertEqual(require_serialized_map(prefix), str(prefix))
            Path(str(prefix) + ".data").write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "empty"):
                require_serialized_map(prefix)

    def test_refuses_directory_instead_of_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "completed_map"
            Path(str(prefix) + ".posegraph").mkdir()
            with self.assertRaisesRegex(ValueError, "serialized map"):
                require_serialized_map(prefix)

    def test_reports_unreadable_file(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "completed_map"
            Path(str(prefix) + ".posegraph").write_bytes(b"fixture")
            with patch.object(Path, "open", side_effect=PermissionError("denied")):
                with self.assertRaisesRegex(ValueError, "unreadable"):
                    require_serialized_map(prefix)

    def test_localization_checks_before_constructing_actions(self):
        tree = ast.parse((REPO / "nav/robot_slam/launch/slam_localization.launch.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and
                        node.name == "generate_launch_description")
        first = function.body[0]
        self.assertIsInstance(first, ast.Assign)
        self.assertIsInstance(first.value, ast.Call)
        self.assertEqual(first.value.func.id, "require_serialized_map")
        self.assertEqual(first.targets[0].id, "map_prefix")
        overrides = [node for node in ast.walk(function) if isinstance(node, ast.Dict) and
                     any(isinstance(key, ast.Constant) and key.value == "map_file_name" for key in node.keys)]
        self.assertEqual(len(overrides), 1)
        value = overrides[0].values[0]
        self.assertIsInstance(value, ast.Name)
        self.assertEqual(value.id, "map_prefix")


if __name__ == "__main__":
    unittest.main()
