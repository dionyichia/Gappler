#!/usr/bin/env python3
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node, SetParameter
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

from gappler_common import path, static_transform_args
from slam_maps import require_initial_pose, require_serialized_map, require_snapshot_manifest


# Where saved maps live: `map_dir` in shared/global_config.yaml, overridden by
# exporting GAPPLER_MAP_DIR. Needs `source nav/nav_env.sh` (or global_env.sh) first, so gappler_common imports.
#   mapping writes  <map_dir>/current_map
#   localisation reads <map_dir>/completed_map
MAP_DIR = str(path("map_dir"))


def generate_launch_description():
    map_prefix = require_serialized_map(os.path.join(MAP_DIR, "completed_map"))
    start_pose = require_initial_pose()
    require_snapshot_manifest(MAP_DIR)
    # Network addresses are an operator prerequisite, not a launch side effect.

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

    # odom_source: wheel (default, unchanged) or fastlivo. In fastlivo mode FAST-LIVO2 owns odom -> robot_base_link through
    # fastlivo_odom_bridge, so the base driver must not publish that TF. The vendor launch starts the driver in a 15 s TimerAction
    # and reads pub_tf once, so the SetParameter group must be unscoped or it closes before the timer fires (measured with stub nodes,
    # T3.5e write-up). The vendor launch is included, not copied. /odom stays on the wheels either way (the mapper's twist is zero).
    odom_source_arg = DeclareLaunchArgument(
        "odom_source", default_value="wheel", choices=["wheel", "fastlivo"],
        description="wheel: the base driver publishes odom -> robot_base_link. fastlivo: FAST-LIVO2 does, through fastlivo_odom_bridge.",
    )
    odom_is_fastlivo = PythonExpression(["'", LaunchConfiguration("odom_source"), "' == 'fastlivo'"])

    # base_driver:=false starts no base driver at all (the live runbook pushes the base by hand and starts the driver once at the end,
    # through base_driver_check.launch.py, to confirm it publishes no odom TF). Default true: both modes start it as before.
    base_driver_arg = DeclareLaunchArgument(
        "base_driver", default_value="true", choices=["true", "false"],
        description="false: do not start the base driver (xnode_comm, xnode_vehicle)",
    )
    base_driver_on = PythonExpression(["'", LaunchConfiguration("base_driver"), "' == 'true'"])

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
        ),
        condition=IfCondition(PythonExpression(["not ", odom_is_fastlivo, " and ", base_driver_on])),
    )
    echo_launch_fastlivo = GroupAction(
        scoped=False,
        condition=IfCondition(PythonExpression([odom_is_fastlivo, " and ", base_driver_on])),
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
    )

    livox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                PathJoinSubstitution(
                    [
                        FindPackageShare("robot_slam"),
                        "launch",
                        "lidar_only.launch.py",
                    ]
                )
            ]
        ),
        # CustomMsg for FAST-LIVO2, PointCloud2 for the SLAM Toolbox path otherwise.
        launch_arguments={"xfer_format": PythonExpression(["1 if ", odom_is_fastlivo, " else 0"])}.items(),
    )

    qos_relay_node = Node(
        package="qos_relay",
        executable="qos_relay.py",
        name="qos_relay",
        output="screen",
        condition=UnlessCondition(odom_is_fastlivo),
    )

    # fastlivo mode: the driver publishes CustomMsg, so this replaces qos_relay (/livox/lidar -> /cloud_relay, best effort).
    custom_to_cloud_node = Node(
        package="robot_slam",
        executable="livox_custom_to_cloud.py",
        name="livox_custom_to_cloud",
        output="screen",
        condition=IfCondition(odom_is_fastlivo),
    )

    # fastlivo mode: odom -> robot_base_link from the mapper's /aft_mapped_to_init. The mapper itself runs outside this launch
    # and must have its own /tf remapped off the shared tree (-r /tf:=/fastlivo/tf -r /tf_static:=/fastlivo/tf_static).
    odom_bridge_node = Node(
        package="robot_slam",
        executable="fastlivo_odom_bridge.py",
        name="fastlivo_odom_bridge",
        output="screen",
        parameters=[os.path.join(get_package_share_directory("robot_slam"), "config", "fastlivo_bridge.yaml")],
        condition=IfCondition(odom_is_fastlivo),
    )

    static_tf_node = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_to_livox",
        arguments=static_transform_args("lidar_mount"),
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
        arguments=static_transform_args("arm_mount"),
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
        # File availability is checked before any hardware actions are constructed.
        # This does not establish graph compatibility or successful localization.
        # Explicit start pose required: map_start_at_dock:=false in yaml would
        # otherwise silently localize at origin.
        parameters=[
            slam_params_file,
            {"map_file_name": map_prefix, "map_start_pose": start_pose},
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

    # Scoped out (CHANNEL_CONTRACT N-1): the return-to-user leg is out of scope, and goto_glasses
    # is a second navigate_to_pose client that drives to the user on any spoken word (CODE_AUDIT E5).
    # Kept, not deleted, so it can come back with the return leg.
    # goto_glasses_node = Node(
    #     package="goto_glasses",
    #     executable="goto_glasses.py",
    #     name="goto_glasses",
    #     output="screen",
    # )

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
    # nav2:=false starts the chain without any Nav2 server (the live runbook: nothing can be sent a goal). Default true, as before.
    nav2_arg = DeclareLaunchArgument("nav2", default_value="true", choices=["true", "false"],
                                     description="false: do not start Nav2 (the 25 s delayed start is skipped)")
    delayed_nav2 = TimerAction(period=25.0, actions=[nav2], condition=IfCondition(LaunchConfiguration("nav2")))

    return LaunchDescription(
        [
            odom_source_arg,
            nav2_arg,
            base_driver_arg,
            robot_state_publisher,
            joint_state_publisher,
            echo_launch,
            echo_launch_fastlivo,
            livox_launch,
            qos_relay_node,
            custom_to_cloud_node,
            odom_bridge_node,
            static_tf_node,
            arm_mount_tf,
            pointcloud_to_laserscan,
            slam_toolbox,
            delayed_nav2,
            pose_publisher_node,
            goal_reached_node,
            # goto_glasses_node,  # scoped out, see above
            aria_image_relay,
            object_approach_node,
            rviz,
        ]
    )
