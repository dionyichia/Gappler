# Arm subsystem: the install/ overlay (built together with grasp by ./build.sh).
#   source <repo>/arm/arm_env.sh
# Sets up only this subsystem, so it can be started on its own. <repo>/global_env.sh sources all four.
# git finds the repo from this file's folder, and stops outside a git clone instead of guessing.
GAPPLER_REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)" || return 1
source "$GAPPLER_REPO/shared/base_envs/ros_humble_and_helper.sh" || return 1
if [ ! -f "$GAPPLER_REPO/install/local_setup.bash" ]; then
  echo "arm_env.sh: no install/ in $GAPPLER_REPO. Run ./build.sh first." >&2
  return 1
fi
source "$GAPPLER_REPO/install/local_setup.bash"
