"""Paused-only diagnostic checks; no ROS or Docker is started."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

import replay


class DiagnosticTests(unittest.TestCase):
    def test_debugger_loads_ros_before_gdb_without_exec_wrapper(self):
        script = Path(__file__).with_name('debug_shutdown.sh').read_text()
        self.assertLess(script.index('source /opt/ros/humble/setup.bash'), script.index('exec /usr/bin/gdb'))
        for required in ('--network none', '--cap-drop ALL', '--user 10001:10001',
                         '--read-only', 't35-fastlivo-debug:shutdown', '-ex "run"'):
            self.assertIn(required, script)
        for forbidden in ('set exec-wrapper', '--privileged', 'SYS_PTRACE', 'ros2 bag play'):
            self.assertNotIn(forbidden, script)

    def test_snapshot_includes_unexpected_compressed_subscription(self):
        endpoint = SimpleNamespace(node_name='t59_republish', topic_type='sensor_msgs/msg/CompressedImage',
                                   qos_profile=SimpleNamespace(reliability='RELIABLE', durability='VOLATILE'))

        class Node:
            def get_topic_names_and_types(self):
                return [('/in/compressed', ['sensor_msgs/msg/CompressedImage'])]

            def get_publishers_info_by_topic(self, topic):
                return []

            def get_subscriptions_info_by_topic(self, topic):
                return [endpoint] if topic == '/in/compressed' else []

        edges = [('/left_camera/image/compressed', 'sensor_msgs/msg/CompressedImage',
                  'rosbag2_player', 't59_republish')]
        rows = {row['topic']: row for row in replay.collect_graph(Node(), edges)}
        self.assertEqual(rows['/left_camera/image/compressed']['subscribers'], [])
        self.assertEqual(rows['/in/compressed']['subscribers'][0]['node'], 't59_republish')

    def test_snapshot_preserves_query_failure(self):
        class Node:
            def get_topic_names_and_types(self):
                raise RuntimeError('discovery failed')

            def get_publishers_info_by_topic(self, topic):
                raise RuntimeError('publishers failed')

            def get_subscriptions_info_by_topic(self, topic):
                return []

        rows = replay.collect_graph(Node(), [('/expected', 'type', 'pub', 'sub')])
        self.assertTrue(any('discovery failed' in str(row) for row in rows))
        self.assertTrue(any('publishers failed' in str(row) for row in rows))

    def test_resume_is_guarded_against_diagnostic_mode(self):
        tree = ast.parse(Path(replay.__file__).read_text())
        guarded = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and ast.unparse(node.test) == 'not diagnostic':
                guarded.extend(ast.walk(node))
        self.assertTrue(any(isinstance(node, ast.Call) and ast.unparse(node.func) == 'resume.call_async'
                            for node in guarded), 'player resume must be inside if not diagnostic')
        wrapper = Path(__file__).with_name('run_replay.sh').read_text()
        self.assertIn('--diagnostic', wrapper)
        self.assertIn('T35_PAUSED_DIAGNOSTIC=$DIAGNOSTIC', wrapper)


if __name__ == '__main__':
    unittest.main()
