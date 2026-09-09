# Source this in every terminal that touches this project:
#   source ~/Desktop/Renaissance-Capstone-Project/env.sh
#
# The repo-root install/ is a single complete overlay: the 2026-08-25 colcon run
# at the repo root picked up BOTH ros2_robot_ws/src and deps_ws/src, so MoveIt
# Task Constructor is already in it. Do NOT also source deps_ws/install --
# it holds a second copy of the same MTC packages.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source /opt/ros/humble/setup.bash
source "$REPO_ROOT/install/setup.bash"
source "$REPO_ROOT/.venv/bin/activate"

echo "ROS overlay: $REPO_ROOT/install   DISPLAY=$DISPLAY"
