"""Attended LiDAR check: no base, arm, autonomy or network configuration."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """Select the driver format explicitly instead of the vendor default: PointCloud2 (0) unless a launch asks for CustomMsg (1)."""
    config = os.path.join(get_package_share_directory("livox_ros_driver2"), "config", "MID360_config.json")
    return LaunchDescription([
        DeclareLaunchArgument("xfer_format", default_value="0", description="0 PointCloud2 (nav), 1 CustomMsg (FAST-LIVO2)"),
        Node(
            package="livox_ros_driver2",
            executable="livox_ros_driver2_node",
            name="livox_lidar_publisher",
            output="screen",
            parameters=[{
                "xfer_format": ParameterValue(LaunchConfiguration("xfer_format"), value_type=int),
                "multi_topic": 0,
                "data_src": 0,
                "publish_freq": 10.0,
                "output_data_type": 0,
                "frame_id": "livox_frame",
                "user_config_path": config,
                "cmdline_input_bd_code": "livox0000000001",
            }],
        ),
    ])
