"""Shared geometry wiring checks; runtime checks also run where PyYAML exists."""
import ast
import importlib.util
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
HAS_YAML = importlib.util.find_spec('yaml') is not None
if HAS_YAML:
    import gappler_common


class GeometryWiring(unittest.TestCase):
    def test_launch_mounts_use_shared_arguments(self):
        for name in ('slam_mapping.launch.py', 'slam_localization.launch.py'):
            tree = ast.parse((ROOT / 'nav/robot_slam/launch' / name).read_text())
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'static_transform_args']
            self.assertEqual(sorted(node.args[0].value for node in calls), ['arm_mount', 'lidar_mount'])

    def test_navigation_references_are_distinct(self):
        approach = (ROOT / 'nav/object_approach/object_approach_node.py').read_text()
        returning = (ROOT / 'nav/goto_glasses/goto_glasses.py').read_text()
        self.assertIn('["legacy_approach_reference_x_m"]', approach)
        self.assertIn('["legacy_return_front_x_m"]', returning)
        self.assertNotIn('CAMERA_X_OFFSET = 0.18', approach + returning)
        self.assertNotIn('t.transform.translation.z + 0.48', approach)


@unittest.skipUnless(HAS_YAML, 'PyYAML absent; runtime geometry checks require lab/ROS environment')
class GeometryRuntime(unittest.TestCase):
    def test_existing_mounts_and_navigation_are_preserved(self):
        self.assertEqual(gappler_common.static_transform_args('arm_mount'),
                         ['0.18', '0.0', '0.48', '3.14159', '0.0', '0.0', 'robot_base_link', 'base_link'])
        self.assertEqual(gappler_common.static_transform_args('lidar_mount'),
                         ['0.18', '0.0', '0.2', '0.0', '0.0', '0.0', 'robot_base_link', 'livox_frame'])
        geometry = gappler_common.config()['geometry']
        self.assertEqual(geometry['legacy_approach_reference_x_m'], 0.18)
        self.assertEqual(geometry['legacy_return_front_x_m'], 0.18)
        self.assertEqual(geometry['d455_bottom_screw']['xyz_m'], [0.208, 0.0, 0.528])

    def test_changed_config_reaches_arguments_and_rpy_order(self):
        data = {'geometry': {'example': {'xyz_m': [1, 2, 3], 'rpy_rad': [0.1, 0.2, 0.3],
                                        'parent': 'parent', 'child': 'child'}}}
        with patch.object(gappler_common, 'config', return_value=data):
            self.assertEqual(gappler_common.static_transform_args('example'),
                             ['1.0', '2.0', '3.0', '0.3', '0.2', '0.1', 'parent', 'child'])
            data['geometry']['example']['xyz_m'][0] = 4
            self.assertEqual(gappler_common.static_transform_args('example')[0], '4.0')

    def test_invalid_mount_rejected(self):
        for xyz in ([1, 2], [math.nan, 0, 0], [math.inf, 0, 0]):
            with patch.object(gappler_common, 'config', return_value={
                    'geometry': {'bad': {'xyz_m': xyz, 'rpy_rad': [0, 0, 0],
                                         'parent': 'a', 'child': 'b'}}}):
                with self.assertRaises(ValueError):
                    gappler_common.static_transform_args('bad')

    def test_invalid_frames_rejected(self):
        for parent, child in (('', 'b'), ('a', ''), ('a', 'a'), (None, 'b')):
            with patch.object(gappler_common, 'config', return_value={
                    'geometry': {'bad': {'xyz_m': [0, 0, 0], 'rpy_rad': [0, 0, 0],
                                         'parent': parent, 'child': child}}}):
                with self.assertRaises(ValueError):
                    gappler_common.static_transform_args('bad')


if __name__ == '__main__':
    if '--runtime' in sys.argv:
        sys.argv.remove('--runtime')
        if not HAS_YAML:
            print('SKIP: runtime geometry tests require existing PyYAML (lab/ROS environment)')
            sys.exit(3)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(GeometryRuntime)
    elif '--wiring' in sys.argv:
        sys.argv.remove('--wiring')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(GeometryWiring)
    else:
        suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner().run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
