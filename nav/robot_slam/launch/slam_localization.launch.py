#!/usr/bin/env python3
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

from gappler_common import path


# Where saved maps live: `map_dir` in shared/global_config.yaml, overridden by
# exporting GAPPLER_MAP_DIR. Needs `source nav/nav_env.sh` (or global_env.sh) first, so gappler_common imports.
#   mapping writes  <map_dir>/current_map
#   localisation reads <map_dir>/completed_map
MAP_DIR = str(path("map_dir"))


def generate_launch_description():
    network_setup = ExecuteProcess(
        cmd=[
            "sudo",
            "bash",
            "-c",
            "ip addr flush dev enp2s0 && ip addr add 192.168.1.5/24 dev enp2s0",
        ],
        output="screen",
    )

    # Robot state publisher (publishes URDF to /robot_description)
    urdf_file_path = PathJoinSubstitution(
        [FindPackageShare("xpkg_urdf_echo_plus"), "urdf", "model.urdf"]
    )
    robot_description = ParameterValue(
        Command(["xacro ", urdf_file_path]), value_type=str
    )
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": robot_description}],
        remappings=[("joint_states", "/base/joint_states"), ("robot_description", "/base/robot_description")],
    )
    joint_state_publisher = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        output="screen",
        remappings=[
            ("joint_states", "/base/joint_states"),
            ("robot_description", "/base/robot_description"),
        ],
    )

    echo_launch = IncludeLaunchDescription(
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
    )

    livox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                PathJoinSubstitution(
                    [
                        FindPackageShare("livox_ros_driver2"),
                        "launch_ROS2",
                        "msg_MID360_launch.py",
                    ]
                )
            ]
        )
    )

    qos_relay_node = Node(
        package="qos_relay",
        executable="qos_relay.py",
        name="qos_relay",
        output="screen",
    )

    static_tf_node = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_to_livox",
        arguments=["0.18", "0", "0.2", "0", "0", "0", "robot_base_link", "livox_frame"],
    )

    # Arm is physically mounted 0.18 m forward and 0.48 m above robot_base_link.
    # Yaw=π rotates the arm frame 180° so its X-axis (forward) aligns with the
    # robot's forward direction (arm was mounted facing backward).
    # This static TF bridges the SLAM tree and the arm tree so object_approach_node
    # can transform directly from base_link (arm frame) → map via TF.
    arm_mount_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="robot_base_to_arm",
        arguments=["0.18", "0", "0.48", "3.14159", "0", "0", "robot_base_link", "base_link"],
    )

    pointcloud_to_laserscan = Node(
        package="pointcloud_to_laserscan",
        executable="pointcloud_to_laserscan_node",
        name="pointcloud_to_laserscan",
        parameters=[
            {
                "target_frame": "livox_frame",
                "transform_tolerance": 0.01,
                "min_height": -0.1,
                "max_height": 0.5,
                "angle_min": -3.14159,
                "angle_max": 3.14159,
                "angle_increment": 0.00872,
                "scan_time": 0.1,
                "range_min": 0.1,
                "range_max": 40.0,
                "use_inf": True,
            }
        ],
        remappings=[("/cloud_in", "/cloud_relay")],
    )

    slam_toolbox_dir = get_package_share_directory("robot_slam")
    slam_params_file = os.path.join(
        slam_toolbox_dir, "config", "slam_toolbox_localization.yaml"
    )

    slam_toolbox = Node(
        package="slam_toolbox",
        executable="localization_slam_toolbox_node",
        name="slam_toolbox",
        output="screen",
        # The params file carries a default; this override is what actually
        # decides, because a ROS params file cannot read an environment variable.
        parameters=[
            slam_params_file,
            {"map_file_name": os.path.join(MAP_DIR, "completed_map")},
        ],
        remappings=[("scan", "/scan")],
        arguments=["--ros-args", "--log-level", "WARN"],
    )

    pose_publisher_node = Node(
        package="pose_publisher",
        executable="pose_publisher.py",
        name="pose_publisher",
        output="screen",
    )

    goal_reached_node = Node(
        package="goal_reached",
        executable="goal_reached_publisher.py",
        name="goal_reached_publisher",
        output="screen",
    )

    goto_glasses_node = Node(
        package="goto_glasses",
        executable="goto_glasses.py",
        name="goto_glasses",
        output="screen",
    )

    aria_image_relay = Node(
        package="aria_image_relay",
        executable="aria_image_relay.py",
        name="aria_image_relay",
        output="screen",
    )

    object_approach_node = Node(
        package="object_approach",
        executable="object_approach_node.py",
        name="object_approach_node",
        output="screen",
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=[
            "-d",
            os.path.join(
                get_package_share_directory("robot_slam"), "config", "slam.rviz"
            ),
            "--ros-args",
            "--log-level",
            "WARN",
        ],
    )
    nav2_params_file = os.path.join(
        get_package_share_directory("robot_slam"), "config", "nav2_params.yaml"
    )

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                PathJoinSubstitution(
                    [FindPackageShare("nav2_bringup"), "launch", "navigation_launch.py"]
                )
            ]
        ),
        launch_arguments={
            "use_sim_time": "false",
            "params_file": nav2_params_file,
        }.items(),
    )
    delayed_nav2 = TimerAction(period=25.0, actions=[nav2])

    return LaunchDescription(
        [
            network_setup,
            robot_state_publisher,
            joint_state_publisher,
            echo_launch,
            livox_launch,
            qos_relay_node,
            static_tf_node,
            arm_mount_tf,
            pointcloud_to_laserscan,
            slam_toolbox,
            delayed_nav2,
            pose_publisher_node,
            goal_reached_node,
            goto_glasses_node,
            aria_image_relay,
            object_approach_node,
            rviz,
        ]
    )
