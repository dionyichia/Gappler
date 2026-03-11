from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder(
        "rm_65_description", package_name="rm_65_w_gripper_config"
    ).to_moveit_configs()

    mtc_node = Node(
        package="rm_mtc",
        executable="mtc_sim_test",
        output="screen",
        parameters=[
            moveit_config.to_dict(),
            {"use_sim_time": True},
        ],
    )

    return LaunchDescription([mtc_node])
