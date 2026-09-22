# INTERNAL: do not source this yourself. Source global_env.sh, or one <subsystem>/<subsystem>_env.sh.
#
# Sources ROS 2 Humble and puts shared/ on PYTHONPATH (so gappler_common imports). Every
# <subsystem>_env.sh sources this after setting GAPPLER_REPO (the repo root).
# Runs once per shell, so sourcing several subsystem files does not repeat it.

[ -n "${GAPPLER_ROS_HUMBLE_AND_HELPER_DONE:-}" ] && return 0
if [ ! -f /opt/ros/humble/setup.bash ]; then
  echo "ros_humble_and_helper.sh: no ROS 2 Humble at /opt/ros/humble on this machine." >&2
  return 1
fi
source /opt/ros/humble/setup.bash
# shared/gappler_common.py is how every program finds paths and global config (NEXT_STEPS 2.15).
export PYTHONPATH="$GAPPLER_REPO/shared${PYTHONPATH:+:$PYTHONPATH}"
export GAPPLER_REPO
GAPPLER_ROS_HUMBLE_AND_HELPER_DONE=1
