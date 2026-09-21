from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder(
        "rm_65_with_gripper", package_name="rm_65_w_gripper_config"
    ).to_moveit_configs()

    grasp_state_machine = Node(
        package="grasp_state_machine",
        executable="grasp_state_machine",
        output="screen",
        parameters=[moveit_config.to_dict()],
    )

    return LaunchDescription([grasp_state_machine])
