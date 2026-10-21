"""Map prerequisites must fail before localization constructs hardware actions."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "shared"))
from slam_maps import (require_initial_pose, require_serialized_map, require_snapshot_manifest,
                          stage_snapshot)


class SlamMapTests(unittest.TestCase):
    def valid_snapshot(self, folder: Path) -> dict:
        files = {"completed_map.posegraph": b"graph", "completed_map.data": b"data",
                 "current_map.pgm": b"P5 fixture", "current_map.yaml": b"image: current_map.pgm\n"}
        for name, content in files.items():
            (folder / name).write_bytes(content)
        manifest = {"frame": "map", "width": 160, "height": 120, "resolution": 0.05,
                    "sha256": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
        (folder / "manifest.json").write_text(json.dumps(manifest))
        return manifest

    def test_snapshot_manifest_accepts_matching_checksums(self):
        with tempfile.TemporaryDirectory(prefix="snapshot with spaces ") as directory:
            folder = Path(directory)
            manifest = self.valid_snapshot(folder)
            self.assertEqual(require_snapshot_manifest(folder), manifest)

    def test_snapshot_manifest_refuses_missing_tampered_and_bad_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with self.assertRaisesRegex(ValueError, "manifest"):
                require_snapshot_manifest(folder)
            manifest = self.valid_snapshot(folder)
            (folder / "current_map.pgm").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "checksum|sha256"):
                require_snapshot_manifest(folder)
            self.valid_snapshot(folder)
            bad = dict(manifest, width=0)
            (folder / "manifest.json").write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, "width|height|resolution|frame"):
                require_snapshot_manifest(folder)
    def test_initial_pose_requires_explicit_finite_xyz(self):
        self.assertEqual(require_initial_pose("0.9,0.5,0.25"), [0.9, 0.5, 0.25])
        for bad in ("", "0.9,0.5", "0.9,0.5,0.25,1", "a,b,c", "1,2,nan", "1,2,inf", None):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(ValueError, "initial pose"):
                    require_initial_pose(bad if bad is None else str(bad))
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

    def test_stage_copies_snapshot_into_independent_files(self):
        with tempfile.TemporaryDirectory(prefix="source with spaces ") as source:
            with tempfile.TemporaryDirectory() as staging:
                folder = Path(source)
                manifest = self.valid_snapshot(folder)
                staged, checked = stage_snapshot(folder, Path(staging))
                self.assertEqual(checked, manifest)
                self.assertEqual(staged.parent, Path(staging))
                for name in ("completed_map.posegraph", "completed_map.data",
                             "current_map.yaml", "current_map.pgm", "manifest.json"):
                    self.assertTrue((staged / name).is_file(), name)
                    self.assertFalse((staged / name).is_symlink(), name)
                (staged / "current_map.pgm").write_bytes(b"staged edit")
                self.assertEqual((folder / "current_map.pgm").read_bytes(), b"P5 fixture")

    def test_stage_refuses_missing_manifest_tampered_and_missing_file(self):
        with tempfile.TemporaryDirectory() as source:
            with tempfile.TemporaryDirectory() as staging:
                with self.assertRaisesRegex(ValueError, "manifest"):
                    stage_snapshot(Path(source), Path(staging))
                manifest = self.valid_snapshot(Path(source))
                (Path(source) / "current_map.pgm").write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "checksum|sha256|mismatch"):
                    stage_snapshot(Path(source), Path(staging))
                self.valid_snapshot(Path(source))
                (Path(source) / "completed_map.data").unlink()
                with self.assertRaisesRegex(ValueError, "unreadable|missing|checksum|sha256"):
                    stage_snapshot(Path(source), Path(staging))

    def test_localization_requires_explicit_start_pose(self):
        tree = ast.parse((REPO / "nav/robot_slam/launch/slam_localization.launch.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and
                        node.name == "generate_launch_description")
        calls = [node.func.id for node in ast.walk(function)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertIn("require_initial_pose", calls, "localization must require explicit start pose, not silent origin")
        self.assertIn("require_snapshot_manifest", calls, "localization must verify the saver manifest, not just file presence")
        start_pose = [node for node in ast.walk(function) if isinstance(node, ast.Dict) and
                      any(isinstance(key, ast.Constant) and key.value == "map_start_pose" for key in node.keys)]
        self.assertEqual(len(start_pose), 1, "map_start_pose override missing")

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
