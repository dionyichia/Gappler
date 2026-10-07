"""Planar camera-referenced stopping geometry, independent of ROS/hardware."""
import importlib
import ast
import math
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))


class CameraNavigation(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'shared/nav_geometry.py').exists(), 'camera-referenced goal geometry missing')
        self.geometry = importlib.import_module('nav_geometry')

    def test_camera_not_base_is_at_clearance_for_rotated_goals(self):
        for clearance in (0.6, 0.5):
            for yaw in (0.0, math.pi / 2, math.pi, -0.7):
                gx, gy = self.geometry.camera_goal_xy(2, -1, yaw, 0.21915, 0.0475, clearance)
                cx = gx + math.cos(yaw) * 0.21915 - math.sin(yaw) * 0.0475
                cy = gy + math.sin(yaw) * 0.21915 + math.cos(yaw) * 0.0475
                self.assertAlmostEqual(math.hypot(2 - cx, -1 - cy), clearance)
                self.assertAlmostEqual(cx, 2 - math.cos(yaw) * clearance)
                self.assertAlmostEqual(cy, -1 - math.sin(yaw) * clearance)

    def test_lateral_camera_offset_changes_base_goal(self):
        self.assertEqual(self.geometry.camera_goal_xy(0, 0, 0, 0.2, 0.05, 0.6), (-0.8, -0.05))

    def test_invalid_geometry_refused(self):
        for clearance in (-1, 0, math.nan, math.inf):
            with self.assertRaises(ValueError):
                self.geometry.camera_goal_xy(0, 0, 0, 0.2, 0, clearance)
        with self.assertRaises(ValueError):
            self.geometry.camera_goal_xy(0, 0, 0, math.nan, 0, 0.6)

    def test_arrival_refuses_start_when_camera_map_tf_is_lost(self):
        # Execute the production callback without ROS: emulate TF disappearing
        # after a valid goal while the static camera mount remains available.
        tree = ast.parse((ROOT / 'nav/object_approach/object_approach_node.py').read_text())
        callback = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                        and node.name == '_on_goal_reached')

        class TfError(Exception):
            pass

        namespace = {'Time': lambda: None, 'TransformException': TfError,
                     'Bool': lambda **kw: SimpleNamespace(**kw), 'String': SimpleNamespace,
                     'CAMERA_FRAME': 'base_d455_depth_optical_frame'}
        exec(compile(ast.Module(body=[callback], type_ignores=[]), '<arrival callback>', 'exec'), namespace)
        starts = []
        warnings = []

        def lookup(target, source, timestamp):
            if target == 'map':
                raise TfError('map localisation unavailable')
            return SimpleNamespace()

        fake = SimpleNamespace(
            _approach_done=True, _last_object_map=object(),
            _tf_buffer=SimpleNamespace(lookup_transform=lookup),
            _manipulation_start_pub=SimpleNamespace(publish=starts.append),
            get_logger=lambda: SimpleNamespace(warn=warnings.append, info=lambda _: None),
        )
        namespace['_on_goal_reached'](fake, SimpleNamespace(data='success'))
        self.assertEqual(starts, [], 'lost map-to-camera TF must not authorise manipulation')
        self.assertTrue(warnings)


if __name__ == '__main__':
    unittest.main()
