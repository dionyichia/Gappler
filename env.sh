# Source this in every terminal that touches the arm workspace, from any directory:
#   source <repo>/env.sh
# Taken from the realman_manip branch on 2026-09-21 (T0.0). Checked on the lab box that day:
# 5 moveit_task_constructor packages, 12 rm_ packages, and the project .venv python.
#
# The repo-root install/ is a single complete overlay. ./build.sh builds
# arm/ and grasp/ into it together, so MoveIt Task Constructor
# is already in it. Do NOT also source an old deps_ws/install, which would add a second copy of
# the same MTC packages. The nav workspace (install_nav/) is not sourced here.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# A copy of this file outside the repo would point at the wrong place and still exit 0.
if [ ! -f "$REPO_ROOT/install/setup.bash" ] || [ ! -f "$REPO_ROOT/.venv/bin/activate" ]; then
  echo "env.sh: no install/ or .venv/ in $REPO_ROOT. Source the env.sh inside the repo," \
       "after ./build.sh and uv sync." >&2
  return 1 2>/dev/null || exit 1
fi

source /opt/ros/humble/setup.bash
source "$REPO_ROOT/install/setup.bash"
source "$REPO_ROOT/.venv/bin/activate"
# shared/gappler_common.py is how every program finds paths and global config (NEXT_STEPS 2.15).
export PYTHONPATH="$REPO_ROOT/shared${PYTHONPATH:+:$PYTHONPATH}"

echo "ROS overlay: $REPO_ROOT/install   DISPLAY=$DISPLAY"
