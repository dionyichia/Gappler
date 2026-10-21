"""Offline config contract checks; stdlib only, not a general YAML validator.

Run: python3 -B -m unittest -v test_replay_config.py
ROS 2 parameter ingestion and replay still require separate runtime checks.
"""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent


class ReplayConfigTests(unittest.TestCase):
    def read_parameters(self, filename: str, node: str) -> dict:
        """Check our deliberately flat YAML layout and JSON-compatible values."""
        path = ROOT / "config" / filename
        self.assertTrue(path.is_file(), f"Missing replay config: {path}")
        lines = [line for line in path.read_text().splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(lines[:2], [f"{node}:", "  ros__parameters:"])
        values = {}
        for line in lines[2:]:
            match = re.fullmatch(r"    ([A-Za-z_][\w.]*): (.+)", line)
            self.assertIsNotNone(match, f"Use one flat parameter per line: {line}")
            key, value = match.groups()
            self.assertNotIn(key, values, f"Duplicate parameter: {key}")
            values[key] = json.loads(value)
        return values

    def assert_parameters(self, actual: dict, expected: dict) -> None:
        self.assertEqual(actual, expected)
        for key, value in expected.items():
            self.assertIs(type(actual[key]), type(value), f"ROS parameter type: {key}")
            if isinstance(value, list):
                for item, expected_item in zip(actual[key], value):
                    self.assertIs(type(item), type(expected_item),
                                  f"ROS array element type: {key}")

    def test_complete_visual_replay_parameters(self) -> None:
        self.assert_parameters(
            self.read_parameters("bright_screen_wall.yaml", "laserMapping"),
            {
                "use_sim_time": True,
                "common.img_topic": "/left_camera/image",
                "common.lid_topic": "/livox/lidar",
                "common.imu_topic": "/livox/imu",
                "common.img_en": 1,
                "common.lidar_en": 1,
                "common.ros_driver_bug_fix": False,
                "common.livox_msg_type": "livox_ros_driver2",
                "extrin_calib.extrinsic_T": [0.04165, 0.02326, -0.0284],
                "extrin_calib.extrinsic_R": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
                "extrin_calib.Rcl": [0.00610193, -0.999863, -0.0154172, -0.00615449, 0.0153796, -0.999863, 0.999962, 0.00619598, -0.0060598],
                "extrin_calib.Pcl": [0.0194384, 0.104689, -0.0251952],
                "time_offset.imu_time_offset": 0.0,
                "time_offset.img_time_offset": 0.1,
                "time_offset.lidar_time_offset": 0.0,
                "time_offset.exposure_time_init": 0.0,
                "rolling_shutter.enable": False,
                "rolling_shutter.tr_readout": 0.0,
                "rolling_shutter.anchor_factor": 0.5,
                "rolling_shutter.debug_print": False,
                "rolling_shutter.td_estimate_enable": False,
                "rolling_shutter.td_step_alpha": 0.1,
                "rolling_shutter.td_step_cap": 0.0005,
                "rolling_shutter.td_lambda": 100.0,
                "rolling_shutter.td_min_jac_sq": 1.0,
                "preprocess.point_filter_num": 1,
                "preprocess.filter_size_surf": 0.1,
                "preprocess.lidar_type": 1,
                "preprocess.scan_line": 6,
                "preprocess.blind": 0.8,
                "preprocess.hilti_en": False,
                "preprocess.feature_extract_enabled": False,
                "vio.max_iterations": 5,
                "vio.outlier_threshold": 1000,
                "vio.img_point_cov": 100,
                "vio.patch_size": 8,
                "vio.patch_pyrimid_level": 4,
                "vio.grid_size": 5,
                "vio.grid_n_height": 17,
                "vio.normal_en": True,
                "vio.raycast_en": False,
                "vio.inverse_composition_en": False,
                "vio.exposure_estimate_en": True,
                "vio.inv_expo_cov": 0.1,
                "imu.imu_en": True,
                "imu.imu_int_frame": 30,
                "imu.acc_cov": 0.5,
                "imu.gyr_cov": 0.3,
                "imu.b_acc_cov": 0.0001,
                "imu.b_gyr_cov": 0.0001,
                "imu.gravity_est_en": True,
                "imu.ba_bg_est_en": True,
                "lio.min_iterations": 5,
                "lio.dept_err": 0.02,
                "lio.beam_err": 0.05,
                "lio.min_eigen_value": 0.0025,
                "lio.voxel_size": 0.5,
                "lio.max_layer": 2,
                "lio.max_points_num": 50,
                "lio.layer_init_num": [5, 5, 5, 5, 5],
                "lio.sigma_num": 3.0,
                "local_map.map_sliding_en": False,
                "local_map.half_map_size": 100,
                "local_map.sliding_thresh": 8.0,
                "uav.imu_rate_odom": False,
                "uav.gravity_align_en": False,
                "publish.dense_map_en": True,
                "publish.pub_effect_point_en": False,
                "publish.pub_plane_en": False,
                "publish.pub_scan_num": 1,
                "publish.blind_rgb_points": 0.0,
                "evo.seq_name": "Bright_Screen_Wall",
                "evo.pose_output_en": False,
                "pcd_save.pcd_save_en": False,
                "pcd_save.type": 0,
                "pcd_save.colmap_output_en": False,
                "pcd_save.filter_size_pcd": 0.15,
                "pcd_save.interval": -1,
                "image_save.img_save_en": False,
                "image_save.interval": 1,
                "debug.plot_time": -10.0,
                "debug.frame_cnt": 6,
            },
        )

    def test_publisher_first_calibration_on_remote_camera_server(self) -> None:
        self.assert_parameters(
            self.read_parameters("camera_pinhole.yaml", "parameter_blackboard"),
            {
                "use_sim_time": True,
                "cam_model": "Pinhole",
                "cam_width": 1280,
                "cam_height": 1024,
                "scale": 0.5,
                "cam_fx": 1293.56944,
                "cam_fy": 1293.3155,
                "cam_cx": 626.91359,
                "cam_cy": 522.799224,
                "cam_d0": -0.076160,
                "cam_d1": 0.123001,
                "cam_d2": -0.00113,
                "cam_d3": 0.000251,
            },
        )

    def test_documents_unverified_extrinsic_and_timestamp_convention(self) -> None:
        path = ROOT / "config" / "bright_screen_wall.yaml"
        self.assertTrue(path.is_file(), f"Missing replay config: {path}")
        text = path.read_text()
        for required in [
            "0d2c0346107b75b59934975adec9a6eeeb913c64",
            "a09599a288c56b832114d7ad9e898248a4111d9e",
            "UNVERIFIED", "LiDAR-to-IMU", "header", "timebase",
            "+ img_time_offset", "Log/", "lio.min_iterations",
        ]:
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
