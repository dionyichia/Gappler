# Navigation subsystem: the install_nav/ overlay (./build.sh nav).
#   source <repo>/nav/nav_env.sh
# Sets up only this subsystem, so it can be started on its own. <repo>/global_env.sh sources all four.
# git finds the repo from this file's folder, and stops outside a git clone instead of guessing.
GAPPLER_REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)" || return 1
source "$GAPPLER_REPO/shared/base_envs/ros_humble_and_helper.sh" || return 1
if [ ! -f "$GAPPLER_REPO/install_nav/local_setup.bash" ]; then
  echo "nav_env.sh: no install_nav/ in $GAPPLER_REPO. Run ./build.sh nav first." >&2
  return 1
fi
source "$GAPPLER_REPO/install_nav/local_setup.bash"
