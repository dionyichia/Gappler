import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Edited urdf file path
    realman_xacro_file = os.path.join(
        get_package_share_directory("rm_description"),
        "urdf",
        "rm_65_w_gripper.urdf.xacro",
    )
    robot_description = Command([FindExecutable(name="xacro"), " ", realman_xacro_file])

    return LaunchDescription(
        [
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                name="arm_state_publisher",
                respawn=True,
                parameters=[{"robot_description": robot_description}],
                remappings=[
                    ("joint_states", "/joint_states"),
                ],
                output="screen",
            )
        ]
    )
