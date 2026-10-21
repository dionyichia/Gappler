#!/usr/bin/env python3
"""Start ONLY the base driver (xnode_comm, xnode_vehicle), with its odom TF off. For the end-of-session check in the T3.5f runbook.

With odom_source:=fastlivo and base_driver:=false the base is pushed by hand with no driver running. At the end, robot still, this launch
starts the driver once so the runbook can confirm it publishes no odom -> robot_base_link (ros2 param get /xnode_vehicle pub_tf, and
tf_edge_check.py), then it is stopped. It sends no command. The parameter is set in an unscoped group because the vendor launch starts
the driver in a 15 s TimerAction and a scoped group closes before that fires (measured with stub nodes, T3.5e). The vendor launch is
included, not copied.
"""
from launch import LaunchDescription
from launch.actions import GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import SetParameter
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        GroupAction(
            scoped=False,
            actions=[
                SetParameter(name="pub_tf", value=False),
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        [
                            PathJoinSubstitution(
                                [
                                    FindPackageShare("xpkg_demo"),
                                    "demo_vehicle/ROS2/launch",
                                    "bringup_basic_ctrl.launch.py",
                                ]
                            )
                        ]
                    )
                ),
            ],
        ),
    ])
