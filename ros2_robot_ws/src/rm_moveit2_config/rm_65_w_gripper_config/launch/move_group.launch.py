from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_move_group_launch


def generate_launch_description():
    moveit_config = (
        MoveItConfigsBuilder(
            "rm_65_with_gripper", package_name="rm_65_w_gripper_config"
        )  # Ensure the monitor is publishing updates so RViz can see them
        .planning_scene_monitor(
            publish_planning_scene=True,
            publish_geometry_updates=True,
            publish_state_updates=True,
            publish_transforms_updates=True,
        )
        .to_moveit_configs()
    )

    moveit_config.move_group_capabilities = {
        "capabilities": "move_group/ExecuteTaskSolutionCapability",
        "disable_capabilities": "",
    }

    return generate_move_group_launch(moveit_config)
