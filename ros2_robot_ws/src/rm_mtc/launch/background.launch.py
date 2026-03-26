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
    rm_65_driver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory(("rm_driver")),
                "launch",
                "rm_65_driver.launch.py",
            )
        )
    )

    rm_65_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("rm_description"),
                "launch",
                "rm_65_display.launch.py",
            )
        ),
    )

    rm_65_control = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory(("rm_control")),
                "launch",
                "rm_65_control.launch.py",
            )
        )
    )

    rm_65_moveit_config = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory(("rm_65_w_gripper_config")),
                "launch",
                "move_group.launch.py",
            )
        )
    )

    return LaunchDescription(
        [rm_65_driver, rm_65_description, rm_65_control, rm_65_moveit_config]
    )
