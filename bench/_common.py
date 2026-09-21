"""Shared constants for the bench tools. Stdlib-only, like the rest of bench/.

OWNED_PREFIXES decides what counts as "our code" (findings fail the bench) as
opposed to vendored code (findings are informational). When the modular reorg
moves code, update it HERE -- otherwise moved files get classified as vendor
and silently stop failing. Paths are repo-relative, matched with startswith.
"""

OWNED_PREFIXES = (
    "src/",
    "shared/",
    "main.py",
    "bench/",
    "ros2_robot_ws/src/rm_mtc/",
    "ros2_robot_ws/install.sh",
    "ros2_robot_ws/src/main.py",
    "ros2_robot_ws/src/orchestrator.py",
    "ros2_robot_ws/src/estop.py",
    "ros2_robot_ws/src/rm_ros_interfaces/",
    "Navigation_Module/src/robot_slam/",
    "Navigation_Module/src/simple_teleop/",
    "Navigation_Module/src/echo_plus_driver/",
    "Navigation_Module/src/robot_navigation/",
)
