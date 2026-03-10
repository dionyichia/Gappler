import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    rm_65_gazebo_up = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory(("rm_gazebo")),
                "launch",
                "gazebo_65_demo.launch.py",
            )
        )
    )
    # Edited to reflect new config
    rm_65_gazebo_moveit = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory(("rm_65_w_gripper_config")),
                "launch",
                "gazebo_moveit_demo.launch.py",
            )
        )
    )

    return LaunchDescription([rm_65_gazebo_up, rm_65_gazebo_moveit])
