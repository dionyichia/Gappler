"""Pure checks: no Docker, ROS, or dataset access."""
import copy
import importlib.util
import math
import re
import signal
import struct
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplayTests(unittest.TestCase):
    def test_raw_images_come_from_offline_bag_without_republish(self):
        supervisor = (HERE / 'replay.py').read_text()
        self.assertIn('"image": "sensor_msgs/msg/Image"', supervisor)
        self.assertIn('params["common.img_topic"]', supervisor)
        self.assertNotIn('image_transport", "republish"', supervisor)
        self.assertNotIn('t59_republish', supervisor)
        self.assertNotIn('CompressedImage', supervisor)

    def test_camera_readiness_uses_humble_parameter_service(self):
        supervisor = (HERE / 'replay.py').read_text()
        self.assertNotIn('rclpy.parameter_client', supervisor)
        self.assertIn('from rcl_interfaces.srv import GetParameters', supervisor)
        self.assertIn('node.create_client(GetParameters, "/parameter_blackboard/get_parameters")', supervisor)

    def test_image_and_asan_options_are_overridable_with_safe_defaults(self):
        wrapper = (HERE / "run_replay.sh").read_text()
        self.assertIn('IMAGE="${T35_REPLAY_IMAGE:-t59-fast-livo2:experimental}"', wrapper)
        self.assertIn('"ASAN_OPTIONS=$ASAN_OPTIONS_VALUE"', wrapper)
        self.assertIn('"LD_PRELOAD=$LD_PRELOAD_VALUE"', wrapper)
        self.assertIn('LD_PRELOAD_VALUE="${T35_LD_PRELOAD:-}"', wrapper)
        self.assertIn('"$IMAGE_ID" "$IMAGE"', wrapper)

    def test_runner_uses_actual_configuration_files(self):
        wrapper = (HERE / 'run_replay.sh').read_text()
        supervisor = (HERE / 'replay.py').read_text()
        for name in ('bright_screen_wall.yaml', 'camera_pinhole.yaml'):
            self.assertTrue((HERE / 'config' / name).is_file())
            self.assertIn(name, wrapper + supervisor)
        self.assertNotIn('bright_screen_wall_camera.yaml', wrapper + supervisor)
        for name in ('t35b_proof3_visual.yaml', 't35b_proof3_lio.yaml', 't35b_proof3_camera.yaml'):
            self.assertTrue((HERE / 'config' / name).is_file())

    def test_bag_configs_and_provenance_are_parameterised_end_to_end(self):
        wrapper = (HERE / 'run_replay.sh').read_text()
        self.assertIn('BAG="${T35_REPLAY_BAG:-', wrapper)
        self.assertIn('MAPPER_CONFIG="${T35_MAPPER_CONFIG:-bright_screen_wall.yaml}"', wrapper)
        self.assertIn('CAMERA_CONFIG="${T35_CAMERA_CONFIG:-camera_pinhole.yaml}"', wrapper)
        self.assertIn('SOURCE_COMMIT="${T35_SOURCE_COMMIT:-', wrapper)
        self.assertIn('--env "T35_MAPPER_CONFIG=$MAPPER_CONFIG"', wrapper)
        self.assertIn('--env "T35_CAMERA_CONFIG=$CAMERA_CONFIG"', wrapper)
        self.assertIn('config/$MAPPER_CONFIG', wrapper)
        self.assertIn('config/$CAMERA_CONFIG', wrapper)
        # No leftover hardcoded list entry can stage a different config than the run reads.
        self.assertNotIn('config/bright_screen_wall.yaml', wrapper)
        self.assertNotIn('config/camera_pinhole.yaml', wrapper)

    def test_public_config_still_derives_the_original_reviewed_inputs(self):
        text = (HERE / 'config' / 'bright_screen_wall.yaml').read_text()

        def value(key):
            return re.search(key + r':\s*"?([^"\n]+)"?', text).group(1).strip().strip('"')

        params = {'common.lid_topic': value('common.lid_topic'),
                  'common.imu_topic': value('common.imu_topic'),
                  'common.img_topic': value('common.img_topic'),
                  'common.img_en': int(value('common.img_en'))}
        self.assertEqual(self.replay.inputs_from_params(params),
                         {'/livox/lidar': 'livox_ros_driver2/msg/CustomMsg',
                          '/livox/imu': 'sensor_msgs/msg/Imu',
                          '/left_camera/image': 'sensor_msgs/msg/Image'})
        self.assertEqual(set(self.replay.outputs_from_params(params)), {'odom', 'cloud', 'rgb'})

    def test_qos_override_covers_every_staged_image_topic(self):
        text = (HERE / 'playback_qos.yaml').read_text()
        blocks = {}
        current = None
        for line in text.splitlines():
            top = re.match(r'^(/[^\s:]+):\s*$', line)
            if top:
                current = top.group(1)
                blocks[current] = []
            elif current is not None and line.strip():
                blocks[current].append(line.strip())
        for name in ('bright_screen_wall.yaml', 't35b_proof3_visual.yaml'):
            config = (HERE / 'config' / name).read_text()
            topic = re.search(r'common\.img_topic:\s*"([^"]+)"', config).group(1)
            with self.subTest(config=name, topic=topic):
                self.assertIn(topic, blocks, 'image topic needs a playback QoS override')
        for topic in ('/livox/lidar', '/livox/imu'):
            self.assertIn(topic, blocks)
        for topic, lines in blocks.items():
            with self.subTest(topic=topic):
                self.assertIn('reliability: reliable', lines)
                self.assertIn('durability: volatile', lines)

    def test_mapper_config_selects_inputs_outputs_and_visual_mode(self):
        ours = {'common.lid_topic': '/livox/lidar', 'common.imu_topic': '/livox/imu',
                'common.img_topic': '/camera/camera/color/image_raw', 'common.img_en': 1}
        self.assertEqual(self.replay.inputs_from_params(ours),
                         {'/livox/lidar': 'livox_ros_driver2/msg/CustomMsg',
                          '/livox/imu': 'sensor_msgs/msg/Imu',
                          '/camera/camera/color/image_raw': 'sensor_msgs/msg/Image'})
        self.assertEqual(set(self.replay.outputs_from_params(ours)), {'odom', 'cloud', 'rgb'})
        lio = dict(ours, **{'common.img_en': 0})
        self.assertEqual(set(self.replay.inputs_from_params(lio)), {'/livox/lidar', '/livox/imu'})
        self.assertEqual(set(self.replay.outputs_from_params(lio)), {'odom', 'cloud'})

    def test_lio_mode_drops_the_visual_gate_but_keeps_both_streams(self):
        streams = {key: {'count': 12, 'first': 1.0, 'last': 7.0, 'invalid': 0}
                   for key in ('odom', 'cloud')}
        lio = {'odom': 'nav_msgs/msg/Odometry', 'cloud': 'sensor_msgs/msg/PointCloud2'}
        self.assertEqual(self.replay.verdict(streams, 0, True, [], outputs=lio,
                                             require_visual=False), 'PASS')
        self.assertEqual(self.replay.verdict(streams, 0, True, [], outputs=lio,
                                             require_visual=True), 'INCONCLUSIVE')
        self.assertEqual(self.replay.verdict(streams, 0, True, [], outputs=None,
                                             require_visual=True), 'FAIL')
        short = {'odom': streams['odom'], 'cloud': dict(streams['cloud'], count=3)}
        self.assertEqual(self.replay.verdict(short, 0, True, [], outputs=lio,
                                             require_visual=False), 'INCONCLUSIVE')

    def test_config_names_are_overridable_basenames_only(self):
        self.assertEqual(self.replay.reviewed_configs({}),
                         ('bright_screen_wall.yaml', 'camera_pinhole.yaml'))
        self.assertEqual(self.replay.reviewed_configs(
            {'T35_MAPPER_CONFIG': 't35b_proof3_visual.yaml',
             'T35_CAMERA_CONFIG': 't35b_proof3_camera.yaml'}),
            ('t35b_proof3_visual.yaml', 't35b_proof3_camera.yaml'))
        for bad in ('../config/x.yaml', 'config/x.yaml', '/tmp/x.yaml', 'x.txt', '', 'x.yaml.gz'):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.replay.reviewed_configs({'T35_MAPPER_CONFIG': bad})

    def test_bag_metadata_topics_must_sum_to_the_message_count(self):
        info = {'starting_time': {'nanoseconds_since_epoch': 10**9},
                'duration': {'nanoseconds': 2 * 10**9}, 'message_count': 3,
                'topics_with_message_count': [
                    {'topic_metadata': {'name': '/livox/lidar',
                                        'type': 'livox_ros_driver2/msg/CustomMsg'},
                     'message_count': 1},
                    {'topic_metadata': {'name': '/camera/camera/color/image_raw',
                                        'type': 'sensor_msgs/msg/Image'}, 'message_count': 2}]}
        expected = self.replay.bag_expectation({'rosbag2_bagfile_information': info})
        self.assertEqual(expected['topics'], {'/livox/lidar': 1,
                                              '/camera/camera/color/image_raw': 2})
        info['message_count'] = 4
        with self.assertRaises(ValueError):
            self.replay.bag_expectation({'rosbag2_bagfile_information': info})

    def setUp(self):
        self.replay = load("replay")

    def test_cloud_reports_reasons_not_just_true_false(self):
        cloud = load("replay").valid_cloud
        import struct
        from types import SimpleNamespace
        good = SimpleNamespace(width=2, height=1, point_step=16, row_step=32,
                               is_bigendian=False, data=struct.pack("<4f", 1, 2, 3, 0) * 2,
                               fields=[SimpleNamespace(name="x", datatype=7, offset=0, count=1),
                                       SimpleNamespace(name="y", datatype=7, offset=4, count=1),
                                       SimpleNamespace(name="z", datatype=7, offset=8, count=1)])
        self.assertEqual(cloud(good), (True, "ok", 0, 2))
        nan_data = struct.pack("<4f", 1, 2, 3, 0) + struct.pack("<4f", float("nan"), 0, 0, 0)
        nan_cloud = SimpleNamespace(width=2, height=1, point_step=16, row_step=32,
                                    is_bigendian=False, data=nan_data,
                                    fields=good.fields)
        self.assertEqual(cloud(nan_cloud)[0:2], (False, "nonfinite_xyz"))
        self.assertEqual(cloud(nan_cloud)[2:], (1, 2))
        empty = SimpleNamespace(width=0, height=1, point_step=16, row_step=0,
                                 is_bigendian=False, data=b"", fields=[])
        self.assertEqual(cloud(empty)[0:2], (False, "empty_or_nonpositive_dimensions"))

    def test_empty_lio_heartbeat_is_neutral_not_invalid(self):
        source = Path(__file__).parent / "replay.py"
        text = source.read_text()
        self.assertIn("cloud_heartbeats", text)
        self.assertIn("in LIVO mode the LIO", text)
        self.assertIn("len(message.data) == 0 and len(message.fields) == 0", text)

    def test_finite_pose_and_unit_quaternion(self):
        self.assertTrue(self.replay.valid_pose([0, 1, 2], [0, 0, 0, 1]))
        for xyz, quat in [([math.nan, 0, 0], [0, 0, 0, 1]),
                          ([0, 0, 0], [0, 0, 0, 0]),
                          ([0, 0, 0], [0, math.inf, 0, 1])]:
            self.assertFalse(self.replay.valid_pose(xyz, quat))

    def test_pass_requires_eof_and_all_streams_and_visual_evidence(self):
        streams = {name: {"count": 10, "first": 1, "last": 6, "invalid": 0}
                   for name in ("odom", "cloud", "rgb")}
        self.assertEqual(self.replay.verdict(streams, 2, True, []), "PASS")
        self.assertNotEqual(self.replay.verdict({}, 2, True, []), "PASS")
        self.assertEqual(self.replay.verdict(streams, 2, False, []), "INCONCLUSIVE")
        self.assertEqual(self.replay.verdict(streams, 0, True, []), "INCONCLUSIVE")
        streams["rgb"]["count"] = 9
        self.assertEqual(self.replay.verdict(streams, 2, True, []), "INCONCLUSIVE")
        streams["rgb"]["invalid"] = 1
        self.assertEqual(self.replay.verdict(streams, 2, True, []), "FAIL")
        self.assertEqual(self.replay.verdict(streams, 2, True, ["crash"]), "FAIL")

    def test_repeated_stamps_not_fresh_and_backward_is_invalid(self):
        stream = self.replay.new_stream()
        for stamp in (1, 1, 2, 1):
            self.replay.observe(stream, stamp, True)
        self.assertEqual(stream["count"], 2)
        self.assertEqual(stream["invalid"], 1)

    def test_player_logged_failure_cannot_pass_with_good_metrics(self):
        streams = {name: {"count": 20, "first": 1, "last": 10, "invalid": 0}
                   for name in ("odom", "cloud", "rgb")}
        for text in ("[ERROR] [player]: bad storage", "[FATAL] broken",
                     "Failed to play: runtime_error", "Failed to publish message"):
            errors = self.replay.player_log_failures([text])
            self.assertTrue(errors)
            self.assertEqual(self.replay.verdict(streams, 3, True, errors), "FAIL")
        self.assertEqual(self.replay.player_log_failures(["[INFO] Playback finished"]), [])

    def test_clock_must_cover_metadata_start_and_end(self):
        expected = self.replay.bag_expectation({"rosbag2_bagfile_information": {
            "starting_time": {"nanoseconds_since_epoch": 100000000000},
            "duration": {"nanoseconds": 66700000000}, "message_count": 123,
            "topics_with_message_count": [
                {"topic_metadata": {"name": "/livox/lidar",
                                    "type": "livox_ros_driver2/msg/CustomMsg"},
                 "message_count": 123}]}})
        self.assertEqual(expected["message_count"], 123)
        clock = {"first": 100.0, "last": 166.5, "backward": False}
        self.assertTrue(self.replay.clock_complete(clock, expected))
        for first, last in ((100, 150), (110, 166.7), (100, 167.1), (None, None)):
            with self.subTest(first=first, last=last):
                self.assertFalse(self.replay.clock_complete(
                    {"first": first, "last": last, "backward": False}, expected))
        clock["backward"] = True
        self.assertFalse(self.replay.clock_complete(clock, expected))
        with self.assertRaises((ValueError, KeyError)):
            self.replay.bag_expectation({})

    def cloud(self, endian=False, datatype=7):
        fmt, size = ("f", 4) if datatype == 7 else ("d", 8)
        point_step = size * 3 + 4
        row_step = point_step * 2 + 8
        data = bytearray(row_step * 2)
        for row in range(2):
            for col in range(2):
                struct.pack_into((">" if endian else "<") + fmt * 3,
                                 data, row * row_step + col * point_step, 1, 2, 3)
        return NS(width=2, height=2, point_step=point_step, row_step=row_step,
                  is_bigendian=endian, data=data,
                  fields=[NS(name=name, datatype=datatype, count=1, offset=i * size)
                          for i, name in enumerate("xyz")])

    def test_cloud_all_xyz_finite_endianness_and_row_padding(self):
        for endian in (False, True):
            for datatype in (7, 8):
                cloud = self.cloud(endian, datatype)
                self.assertEqual(self.replay.valid_cloud(cloud)[0], True)
                fmt = (">" if endian else "<") + ("f" if datatype == 7 else "d")
                offset = cloud.row_step + cloud.point_step + cloud.fields[2].offset
                for bad in (math.nan, math.inf, -math.inf):
                    struct.pack_into(fmt, cloud.data, offset, bad)
                    self.assertEqual(self.replay.valid_cloud(cloud)[0:2], (False, "nonfinite_xyz"))

    def test_cloud_rejects_missing_xyz_wrong_fields_and_layout(self):
        for change in (lambda c: c.fields.pop(),
                       lambda c: setattr(c.fields[0], "datatype", 6),
                       lambda c: setattr(c.fields[0], "count", 2),
                       lambda c: setattr(c.fields[0], "offset", c.point_step),
                       lambda c: setattr(c.fields[0], "offset", -1),
                       lambda c: setattr(c.fields[1], "name", "x"),
                       lambda c: setattr(c, "row_step", 1),
                       lambda c: setattr(c, "width", 0),
                       lambda c: setattr(c, "data", b"short")):
            cloud = self.cloud()
            change(cloud)
            self.assertEqual(self.replay.valid_cloud(cloud)[0], False)

    def test_image_requires_bgr8_and_full_rows(self):
        good = NS(width=2, height=2, step=8, encoding="bgr8", data=b"x" * 16)
        self.assertTrue(self.replay.valid_image(good))
        for key, value in (("encoding", "rgb8"), ("step", 5), ("width", 0),
                           ("height", -1), ("data", b"short")):
            bad = copy.copy(good)
            setattr(bad, key, value)
            self.assertFalse(self.replay.valid_image(bad))

    def test_group_exists_handles_absence_and_permission_denial(self):
        for failure, expected in ((ProcessLookupError(), False), (PermissionError(), True)):
            with patch.object(self.replay.os, "killpg", side_effect=failure):
                self.assertEqual(self.replay.group_exists(1234), expected)

    def test_cleanup_waits_for_descendant_after_leader_exit(self):
        leader = Mock(pid=1234)
        leader.poll.return_value = 0
        # Deterministic group status models an exited leader plus live descendant.
        with patch.object(self.replay, "group_exists", side_effect=[True, True, False, False, False]), \
             patch.object(self.replay.os, "killpg") as kill, \
             patch.object(self.replay.time, "sleep") as sleep:
            errors = self.replay.cleanup_groups({"mapper": leader})
        self.assertEqual(errors, [])
        kill.assert_called_once_with(1234, signal.SIGINT)
        sleep.assert_called_once()
        self.assertGreaterEqual(leader.poll.call_count, 2)

    def test_cleanup_survivor_and_sigkill_are_failures(self):
        leader = Mock(pid=1234)
        leader.poll.return_value = 0
        with patch.object(self.replay, "group_exists", return_value=True), \
             patch.object(self.replay.os, "killpg"), \
             patch.object(self.replay.time, "monotonic", side_effect=range(0, 1000, 10)):
            errors = self.replay.cleanup_groups({"mapper": leader})
        self.assertTrue(any("SIGKILL" in error for error in errors))
        self.assertTrue(any("surviv" in error for error in errors))

    def test_cleanup_returncodes_do_not_hide_crashes(self):
        for code in (0, -signal.SIGINT, -signal.SIGTERM):
            self.assertTrue(self.replay.intentional_returncode(code))
        for code in (None, -11, -signal.SIGKILL, 1, 130):
            self.assertFalse(self.replay.intentional_returncode(code))

    def test_no_interactive_custody_prompt_remains(self):
        # Entering the command is the confirmation; programmatic checks below stay.
        wrapper = (HERE / 'run_replay.sh').read_text()
        self.assertNotIn('read -r -p', wrapper)
        self.assertNotIn('CUSTODY AGREED', wrapper)
        self.assertIn('check_conflicts', wrapper)

    def test_wrapper_shutdown_is_named_bounded_and_gates_final_evidence(self):
        wrapper = (HERE / "run_replay.sh").read_text()
        self.assertIn('timeout -k 5s 20s sudo -n docker wait "$C"', wrapper)
        self.assertIn('sudo -n docker kill --signal SIGKILL "$C"', wrapper)
        self.assertIn('timeout -k 5s 10s sudo -n docker wait "$C"', wrapper)
        self.assertIn('if ! confirm_stopped; then', wrapper)
        self.assertIn('CRITICAL custody unresolved', wrapper)
        self.assertIn('custody-unresolved', wrapper)
        self.assertIn('container.state-unconfirmed.inspect.json', wrapper)
        self.assertNotIn('docker stop', wrapper)
        self.assertNotIn('pkill', wrapper)
        self.assertNotIn('docker kill $(', wrapper)

    def test_wrapper_rechecks_expanded_conflicts_before_start(self):
        wrapper = (HERE / "run_replay.sh").read_text()
        for marker in ("Runner", "Worker", "bench/run", "realsense", "xnode_vehicle"):
            self.assertIn(marker, wrapper)
        self.assertGreaterEqual(wrapper.count('\ncheck_conflicts\n'), 2)
        self.assertLess(wrapper.rindex('\ncheck_conflicts\n'), wrapper.index('sudo -n docker start "$C"'))

    def test_unresolved_shutdown_retains_kernel_lock_without_blocking_wrapper(self):
        wrapper = (HERE / "run_replay.sh").read_text()
        self.assertIn('custody-lock-keeper.pid', wrapper)
        self.assertIn('os.fstat(9)', wrapper)
        self.assertIn('while hold.exists():', wrapper)
        self.assertIn('9>&9 &', wrapper)
        self.assertNotIn('flock -u', wrapper)


class ContainerTests(unittest.TestCase):
    def setUp(self):
        self.check = load("verify_replay_container")
        self.doc = {
            "Image": "sha256:test", "State": {"Status": "created", "Running": False},
            "Mounts": [],
            "NetworkSettings": {"Networks": {"none": {}}},
            "Config": {"Image": "t59-fast-livo2:experimental", "User": "10001:10001",
                       "WorkingDir": "/fast_livo_ws", "Entrypoint": ["/bin/bash"],
                       "Cmd": ["-c", self.check.COMMAND],
                       "Env": [f"{k}={v}" for k, v in self.check.ENV.items()]},
            "HostConfig": {"NetworkMode": "none", "Privileged": False,
                           "CapAdd": None, "CapDrop": ["ALL"],
                           "SecurityOpt": ["no-new-privileges:true"],
                           "Memory": 8 * 1024**3, "MemorySwap": 8 * 1024**3,
                           "NanoCpus": 2000000000, "PidsLimit": 512,
                           "Binds": None, "Devices": [], "DeviceRequests": None,
                           "PortBindings": {}, "PublishAllPorts": False,
                           "PidMode": "", "IpcMode": "private", "ReadonlyRootfs": False,
                           "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                           "AutoRemove": False}}

    def test_exact_expected_container(self):
        self.check.validate(self.doc, "sha256:test")

    def test_image_tag_override_is_explicit(self):
        with self.assertRaises(ValueError):
            self.check.validate(self.doc, "sha256:test", "t35-fastlivo-asan:experimental")
        doc = copy.deepcopy(self.doc)
        doc["Config"]["Image"] = "t35-fastlivo-asan:experimental"
        self.check.validate(doc, "sha256:test", "t35-fastlivo-asan:experimental")

    def test_extra_asan_options_env_passes_validation(self):
        doc = copy.deepcopy(self.doc)
        doc["Config"]["Env"] = doc["Config"]["Env"] + ["ASAN_OPTIONS=detect_leaks=0"]
        self.check.validate(doc, "sha256:test")

    def test_fail_closed_mutations(self):
        mutations = [("HostConfig", "NetworkMode", "host"),
                     ("HostConfig", "Privileged", True),
                     ("HostConfig", "CapAdd", ["SYS_ADMIN"]),
                     ("HostConfig", "MemorySwap", -1),
                     ("HostConfig", "Devices", [{"PathOnHost": "/dev/x"}]),
                     ("HostConfig", "RestartPolicy", {"Name": "always"}),
                     ("NetworkSettings", "Networks", {"none": {}, "bridge": {}}),
                     ("Config", "User", "0"),
                     ("Config", "Env", ["ROS_DOMAIN_ID=127"]),
                     ("State", "Status", "exited")]
        for section, key, value in mutations:
            with self.subTest(key=key):
                doc = copy.deepcopy(self.doc)
                doc[section][key] = value
                with self.assertRaises(ValueError):
                    self.check.validate(doc, "sha256:test")
        for key in ("HostConfig", "Mounts", "Config"):
            doc = copy.deepcopy(self.doc)
            del doc[key]
            with self.assertRaises((ValueError, KeyError)):
                self.check.validate(doc, "sha256:test")
        with self.assertRaises(ValueError):
            self.check.validate(self.doc, "sha256:other")


if __name__ == "__main__":
    unittest.main()
