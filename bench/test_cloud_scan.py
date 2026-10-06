"""Stdlib fixture/profile checks for the synthetic ROS scan bench."""
import math
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "nodes"))
from test_cloud_scan_pipeline import cloud_bytes, converter_parameters, converter_routes, expected_bins, relay_qos_contract


class CloudScanTests(unittest.TestCase):
    def test_livox_xyz_payload_stride(self):
        payload = cloud_bytes([(2.0, 3.0, 0.2), (-1.0, 0.0, 0.1)])
        self.assertEqual(len(payload), 52)
        self.assertAlmostEqual(struct.unpack_from("<f", payload, 8)[0], 0.2)
        self.assertEqual(struct.unpack_from("<fff", payload, 26)[:2], (-1.0, 0.0))

    def test_expected_cardinal_bins_nearest_and_filters(self):
        params = {"min_height": -0.1, "max_height": 0.5, "range_min": 0.1,
                  "range_max": 40.0, "angle_min": -math.pi, "angle_max": math.pi,
                  "angle_increment": math.pi / 4}
        points = [(2, 0, 0.2), (4, 0, 0.2), (0, 3, 0.2), (0, -1.5, 0.2),
                  (1, 1, 2), (0.01, 0, 0.2), (50, 0, 0.2), (math.nan, 1, 0.2)]
        self.assertEqual(expected_bins(points, params), {4: 2.0, 6: 3.0, 2: 1.5})

    def test_profiles_come_from_owned_launches(self):
        for name in ("slam_mapping", "slam_localization", "navigation"):
            params = converter_parameters(name)
            self.assertEqual(params["target_frame"], "livox_frame")
            self.assertTrue(params["use_inf"])
            self.assertLess(params["min_height"], params["max_height"])
            self.assertGreater(params["range_max"], params["range_min"])
        self.assertEqual(converter_parameters("slam_mapping"), converter_parameters("slam_localization"))
        self.assertNotEqual(converter_parameters("navigation")["range_min"], converter_parameters("slam_mapping")["range_min"])

    def test_routes_are_read_from_returned_source_actions(self):
        self.assertEqual(converter_routes("slam_mapping"), ("/cloud_relay", "/scan"))
        self.assertEqual(converter_routes("navigation"), ("/livox/lidar", "/livox/lidar_2d"))
        source = (Path(__file__).resolve().parents[1] / "nav/robot_slam/launch/slam_mapping.launch.py").read_text()
        mutations = [source.replace('("/cloud_in", "/cloud_relay")', '("/cloud_in", "/wrong_cloud")'),
                     source.replace("            pointcloud_to_laserscan,\n", ""),
                     source.replace("            qos_relay_node,\n", "")]
        for text in mutations:
            with patch("pathlib.Path.read_text", return_value=text):
                with self.assertRaises(ValueError):
                    converter_routes("slam_mapping")

    def test_declared_relay_qos_is_used_by_constructor(self):
        contract = relay_qos_contract()
        for role, reliability in (("input", "RELIABLE"), ("output", "BEST_EFFORT")):
            self.assertEqual(contract[role], {"reliability": reliability, "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10})
        source = (Path(__file__).resolve().parents[1] / "nav/qos_relay/qos_relay.py").read_text()
        with patch("pathlib.Path.read_text", return_value=source.replace('TOPICS["cloud_relay"], BEST_EFFORT_QOS', 'TOPICS["cloud_relay"], RELIABLE_QOS')):
            with self.assertRaises(ValueError):
                relay_qos_contract()


if __name__ == "__main__":
    unittest.main()
