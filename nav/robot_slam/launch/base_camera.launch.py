"""Opt-in D455-only launch: measured mount, Intel body model, driver sensor TFs.

Requires the subsystem environment for gappler_common. No base or arm driver is
started. Mount orientation is provisional; camera–LiDAR calibration is separate.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import xacro

from gappler_common import ROOT, camera_serial, config, static_transform_args


def generate_launch_description():
    """Build the camera's two-publisher TF chain without nominal sensor joints."""
    static_transform_args("d455_bottom_screw")  # validates geometry before startup
    mount = config()["geometry"]["d455_bottom_screw"]
    suffix = "_bottom_screw_frame"
    if not mount["child"].endswith(suffix):
        raise ValueError("D455 child must end in _bottom_screw_frame")
    name = mount["child"][:-len(suffix)]
    if not name:
        raise ValueError("D455 requires a unique nonempty camera frame prefix")
    description = xacro.process_file(
        str(ROOT / "nav/robot_slam/urdf/base_d455.urdf.xacro"),
        mappings={"parent": mount["parent"], "name": name,
                  "xyz": " ".join(map(str, mount["xyz_m"])),
                  "rpy": " ".join(map(str, mount["rpy_rad"]))},
    ).toxml()
    mount_publisher = Node(
        package="robot_state_publisher", executable="robot_state_publisher",
        name="base_d455_mount_publisher", namespace="base_camera",
        parameters=[{"robot_description": description}], output="screen",
    )
    driver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory("realsense2_camera"), "launch", "rs_launch.py")),
        launch_arguments={
            "serial_no": "_" + camera_serial("mobile_base_camera"),
            "camera_namespace": "base_camera", "camera_name": name,
            "base_frame_id": "link", "publish_tf": "true",
            "enable_color": "true", "enable_depth": "true",
            "enable_infra1": "false", "enable_infra2": "false",
            "pointcloud.enable": "false",
        }.items(),
    )
    return LaunchDescription([mount_publisher, driver])
