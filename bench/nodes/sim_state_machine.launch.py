"""MoveIt + a SIMULATED RM65 (mock_components) + the grasp_state_machine package, for the bench.

The state machine gets the same parameters as its own launch file
(grasp_state_machine/launch/grasp_state_machine.launch.py: moveit_config.to_dict()), except that the robot
model is bench/nodes/sim_arm.urdf.xacro, whose ros2_control block is fake hardware. Run only
through bench/state_machine_sim.sh, which proves the channel is private, the hardware is
simulated and the real arm is unreachable before this starts.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_demo_launch

HERE = os.path.dirname(os.path.realpath(__file__))


def generate_launch_description():
    cfg = os.path.join(get_package_share_directory("rm_65_w_gripper_config"), "config")
    moveit_config = (
        MoveItConfigsBuilder("rm_65_with_gripper", package_name="rm_65_w_gripper_config")
        .robot_description(file_path=os.path.join(HERE, "sim_arm.urdf.xacro"),
                           mappings={"initial_positions_file": os.path.join(cfg, "initial_positions.yaml")})
        .to_moveit_configs()
    )
    state_machine = Node(package="grasp_state_machine", executable="grasp_state_machine", output="screen",
                         parameters=[moveit_config.to_dict()])
    return LaunchDescription([*generate_demo_launch(moveit_config).entities, state_machine])
