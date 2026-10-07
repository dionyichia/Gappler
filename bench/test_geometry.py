"""Shared geometry wiring checks; runtime checks also run where PyYAML exists."""
import ast
import importlib.util
import math
import sys
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
HAS_YAML = importlib.util.find_spec('yaml') is not None
if HAS_YAML:
    import gappler_common


class GeometryWiring(unittest.TestCase):
    def test_camera_launch_is_camera_only_and_serial_selected(self):
        path = ROOT / 'nav/robot_slam/launch/base_camera.launch.py'
        self.assertTrue(path.exists(), 'camera-only mount/driver launch is missing')
        source = path.read_text()
        self.assertIn('camera_serial("mobile_base_camera")', source)
        self.assertIn('"publish_tf": "true"', source)
        self.assertIn('"robot_state_publisher"', source)
        self.assertNotIn('rm_driver', source)
        self.assertNotIn('bringup_basic_ctrl', source)

    def test_launch_mounts_use_shared_arguments(self):
        for name in ('slam_mapping.launch.py', 'slam_localization.launch.py'):
            tree = ast.parse((ROOT / 'nav/robot_slam/launch' / name).read_text())
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'static_transform_args']
            self.assertEqual(sorted(node.args[0].value for node in calls), ['arm_mount', 'lidar_mount'])

    def test_navigation_references_are_distinct(self):
        approach = (ROOT / 'nav/object_approach/object_approach_node.py').read_text()
        returning = (ROOT / 'nav/goto_glasses/goto_glasses.py').read_text()
        self.assertIn('camera_reference_frame()', approach)
        self.assertIn('camera_reference_frame()', returning)
        self.assertNotIn('legacy_approach_reference_x_m', approach)
        self.assertNotIn('legacy_return_front_x_m', returning)
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
        self.assertEqual(gappler_common.camera_reference_frame(), 'base_d455_depth_optical_frame')
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


@unittest.skipUnless(HAS_YAML and shutil.which('xacro'), 'installed ROS/xacro required for camera-model checks')
class CameraModel(unittest.TestCase):
    def test_intel_owns_body_offset_and_driver_owns_sensors(self):
        mount = gappler_common.config()['geometry']['d455_bottom_screw']
        output = subprocess.check_output([
            'xacro', str(ROOT / 'nav/robot_slam/urdf/base_d455.urdf.xacro'),
            'parent:=' + mount['parent'], 'name:=base_d455',
            'xyz:=' + ' '.join(map(str, mount['xyz_m'])),
            'rpy:=' + ' '.join(map(str, mount['rpy_rad'])),
        ], text=True)
        model = ET.fromstring(output)
        self.assertEqual({link.attrib['name'] for link in model.findall('link')},
                         {'robot_base_link', 'base_d455_bottom_screw_frame', 'base_d455_link'})
        joints = {joint.find('child').attrib['link']: joint for joint in model.findall('joint')}
        self.assertEqual(len(joints), 2, 'nominal sensor TFs must not duplicate driver extrinsics')
        xyz = lambda joint: list(map(float, joint.find('origin').attrib['xyz'].split()))
        self.assertEqual(xyz(joints['base_d455_bottom_screw_frame']), mount['xyz_m'])
        for actual, expected in zip(xyz(joints['base_d455_link']), [0.01115, 0.0475, 0.0145]):
            self.assertAlmostEqual(actual, expected, places=8)
        self.assertEqual(gappler_common.camera_serial('mobile_base_camera'), '146222253541')


if __name__ == '__main__':
    if '--camera-model' in sys.argv:
        sys.argv.remove('--camera-model')
        if not HAS_YAML or not shutil.which('xacro'):
            print('SKIP: camera model checks require installed PyYAML and ROS/xacro')
            sys.exit(3)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(CameraModel)
    elif '--runtime' in sys.argv:
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
