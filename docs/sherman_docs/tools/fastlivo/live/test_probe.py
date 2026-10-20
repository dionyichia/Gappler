"""T3.5d container probe: the safety envelope is fixed in text. No Docker, no ROS."""
from pathlib import Path
import re
import subprocess
import unittest

HERE = Path(__file__).parent
CONTAINER = (HERE / 't35d_probe_container.sh').read_text()
PLAYER = (HERE / 't35d_probe_player.sh').read_text()


class ProbeTests(unittest.TestCase):
    def test_container_keeps_the_replay_envelope_except_network_and_ipc(self):
        for required in ('--cap-drop ALL', '--security-opt no-new-privileges:true',
                         '--pids-limit 512', '--memory 8g', '--cpus 2', '--network host',
                         '--ipc host', '--env ROS_DOMAIN_ID=174', '--env ROS_LOCALHOST_ONLY=1',
                         '-v "$HERE/config:/cfg:ro"'):
            with self.subTest(required=required):
                self.assertIn(required, CONTAINER)

    def test_container_cannot_reach_hardware_docker_or_the_shared_checkout(self):
        for forbidden in ('--privileged', '--device', '--cap-add', '-v /dev', 'docker.sock',
                          'rcp-Gappler/install', '--user 0', '--user root', '--pid host'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, CONTAINER)
        # Only the probe's own output directory is mounted writable.
        writable = [m.split(':')[0] for m in re.findall(r'-v "([^"]+)"', CONTAINER)
                    if not m.endswith(':ro')]
        self.assertTrue(writable and all(h == '$OUT' or h.startswith('$OUT/') for h in writable),
                        writable)

    def test_mapper_starts_only_after_the_camera_service_answers(self):
        # The runbook requires the parameter server to be serving before the mapper
        # loads its camera; a fixed sleep raced and the mapper aborted.
        self.assertIn('ros2 param get /parameter_blackboard cam_model', CONTAINER)
        self.assertNotIn('sleep 4', CONTAINER)
        self.assertLess(CONTAINER.index('ros2 param get /parameter_blackboard cam_model'),
                        CONTAINER.index('fastlivo_mapping --ros-args'))

    def test_player_is_bag_only_and_uses_the_same_private_domain(self):
        self.assertIn('ROS_DOMAIN_ID=174', PLAYER)
        self.assertIn('ROS_LOCALHOST_ONLY=1', PLAYER)
        self.assertIn('ros2 bag play', PLAYER)
        for forbidden in ('/cmd_vel', 'rm_driver', 'ros2 launch', 'ros2 topic pub'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, PLAYER)

    def test_both_scripts_parse_and_stop_on_error(self):
        for name in ('t35d_probe_container.sh', 't35d_probe_player.sh'):
            with self.subTest(name=name):
                self.assertTrue((HERE / name).read_text().startswith('#!/usr/bin/env bash'))
                self.assertIn('set -euo pipefail', (HERE / name).read_text())
                subprocess.run(['bash', '-n', str(HERE / name)], check=True)


if __name__ == '__main__':
    unittest.main()
