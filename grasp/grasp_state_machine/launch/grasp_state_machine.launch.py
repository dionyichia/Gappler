from gappler_common import ROOT
from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder

# Read from the repo, not install/, so editing a config file needs no rebuild. Later files win.
CONFIG_FILES = [str(ROOT / "shared/global_config.yaml"), str(ROOT / "grasp/grasp_config.yaml")]


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder(
        "rm_65_with_gripper", package_name="rm_65_w_gripper_config"
    ).to_moveit_configs()

    grasp_state_machine = Node(
        package="grasp_state_machine",
        executable="grasp_state_machine",
        output="screen",
        parameters=[moveit_config.to_dict(), *CONFIG_FILES],
    )

    return LaunchDescription([grasp_state_machine])
