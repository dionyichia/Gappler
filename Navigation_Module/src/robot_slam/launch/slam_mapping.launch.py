import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


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

    # Auto-saves the map every 30 s during mapping so progress is not lost
    map_autosave = ExecuteProcess(
        cmd=[
            "bash",
            "-c",
            "while true; do sleep 30; "
            "ros2 run nav2_map_server map_saver_cli -f ~/maps/current_map "
            "--ros-args -p save_map_timeout:=5.0; done",
        ],
        output="screen",
    )

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
    )
    joint_state_publisher = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        output="screen",
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

    # QoS relay: bridges RELIABLE livox → BEST_EFFORT for pointcloud_to_laserscan
    qos_relay_node = Node(
        package="robot_slam",
        executable="qos_relay.py",
        name="qos_relay",
        output="screen",
    )

    # Static TF: robot_base_link → livox_frame (LiDAR offset from robot centre)
    static_tf_node = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_to_livox",
        arguments=["0.18", "0", "0.2", "0", "0", "0", "robot_base_link", "livox_frame"],
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
    slam_params_file = os.path.join(slam_toolbox_dir, "config", "slam_toolbox.yaml")

    slam_toolbox = Node(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        output="screen",
        parameters=[slam_params_file],
        remappings=[("scan", "/scan")],
        arguments=["--ros-args", "--log-level", "WARN"],
    )

    pose_publisher_node = Node(
        package="robot_slam",
        executable="pose_publisher.py",
        name="pose_publisher",
        output="screen",
    )
    goal_reached_node = Node(
        package="robot_slam",
        executable="goal_reached_publisher.py",
        name="goal_reached_publisher",
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
            map_autosave,
            robot_state_publisher,
            joint_state_publisher,
            echo_launch,
            livox_launch,
            qos_relay_node,
            static_tf_node,
            pointcloud_to_laserscan,
            slam_toolbox,
            delayed_nav2,
            pose_publisher_node,
            goal_reached_node,
            rviz,
        ]
    )
