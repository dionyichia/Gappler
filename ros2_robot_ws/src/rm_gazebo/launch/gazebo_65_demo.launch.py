import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    ExecuteProcess,
    IncludeLaunchDescription,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_name = "rm_gazebo"

    robot_name_in_model = "rm_65_description"

    pkg_share = FindPackageShare(package=package_name).find(package_name)
    urdf_model_path = os.path.join(
        pkg_share, f"config/gazebo_65_w_gripper_description.urdf.xacro"
    )

    print("---", urdf_model_path)

    doc = xacro.parse(open(urdf_model_path))
    xacro.process_doc(doc)
    params = {"robot_description": doc.toxml()}

    print("urdf", doc.toxml())

    # 启动gazebo
    gazebo = ExecuteProcess(
        cmd=[
            "gazebo",
            "--verbose",
            "-s",
            "libgazebo_ros_init.so",
            "-s",
            "libgazebo_ros_factory.so",
        ],
        output="screen",
    )

    # After starting the robot_state_publisher node, it will publish the robot_description
    # topic, the content of which is the content of the model file urdf.
    # It will also subscribe to the /joint_states topic, retrieve joint data, and then
    # publish the tf and tf_static topics.
    node_robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[{"use_sim_time": True}, params, {"publish_frequency": 15.0}],
        output="screen",
    )

    spawn_entity = Node(
        package="gazebo_ros",
        executable="spawn_entity.py",
        arguments=["-topic", "robot_description", "-entity", f"{robot_name_in_model}"],
        output="screen",
    )

    # When Gazbo loads the URDF, will it start a `joint_states` node based on the URDF
    # settings?
    # Joint state publisher
    load_joint_state_controller = ExecuteProcess(
        cmd=[
            "ros2",
            "control",
            "load_controller",
            "--set-state",
            "active",
            "joint_state_broadcaster",
        ],
        output="screen",
    )

    # Path execution controller, i.e., the action?
    # This rm_group_controller needs to be determined
    # based on the name in ros2_controllers.yaml referenced in the URDF file.
    load_joint_trajectory_controller = ExecuteProcess(
        cmd=[
            "ros2",
            "control",
            "load_controller",
            "--set-state",
            "active",
            "rm_group_controller",
        ],
        output="screen",
    )

    # Gripper controller load
    load_gripper_controller = ExecuteProcess(
        cmd=[
            "ros2",
            "control",
            "load_controller",
            "--set-state",
            "active",
            "gripper_controller",
        ],
        output="screen",
    )

    # The following two parameters are used to control the
    # startup order of each node.

    # Listen to spawn_entity_cmd; when it exits (fully starts),
    # start load_joint_state_controller.
    close_evt1 = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_entity,
            on_exit=[load_joint_state_controller],
        )
    )
    # Monitor load_joint_state_controller; when it exits (fully starts),
    # start load_joint_trajectory_controller.
    # How does moveit connect with the actions provided by Gazebo?
    close_evt2 = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=load_joint_state_controller,
            on_exit=[load_joint_trajectory_controller],
        )
    )

    # Add event handler for gripper controller
    close_evt3 = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=load_joint_trajectory_controller,
            on_exit=[load_gripper_controller],
        )
    )

    ld = LaunchDescription(
        [
            close_evt1,
            close_evt2,
            close_evt3,
            gazebo,
            node_robot_state_publisher,
            spawn_entity,
        ]
    )

    return ld
