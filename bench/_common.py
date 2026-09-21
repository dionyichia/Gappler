"""Shared constants for the bench tools. Stdlib-only, like the rest of bench/.

OWNED_PREFIXES decides what counts as "our code" (findings fail the bench) as
opposed to vendored code (findings are informational). When the modular reorg
moves code, update it HERE -- otherwise moved files get classified as vendor
and silently stop failing. Paths are repo-relative, matched with startswith.
"""

OWNED_PREFIXES = (
    "shared/",
    "main.py",
    "bench/",
    "launchers/",
    "aria/aria_app/",
    "arm/estop/",
    "arm/arm_bringup/",
    "grasp/grasp_state_machine/",
    "grasp/grasp_interfaces/",
    "grasp/anygrasp_node/",
    "grasp/segmentation/",
    "grasp/grasp_viz/",
    "grasp/tools/",
    "nav/robot_slam/",
    "nav/simple_teleop/",
    "nav/echo_plus_driver/",
    "nav/robot_navigation/",
    "build.sh",
    "env.sh",
)
