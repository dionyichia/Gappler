"""MoveIt + a SIMULATED RM65 (mock_components) for the bench. Never rm_driver.

Same as rm_65_w_gripper_config's demo.launch.py, except the robot model comes
from bench/nodes/sim_arm.urdf.xacro, which actually attaches the fake hardware.
Run only through bench/sim_moveit.sh, which checks the channel is private and
that no real driver exists first.
"""
import os

from ament_index_python.packages import get_package_share_directory
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
    return generate_demo_launch(moveit_config)
