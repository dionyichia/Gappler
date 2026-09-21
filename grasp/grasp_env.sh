# Grasp subsystem: the install/ overlay (shared with arm), and the project .venv for the SAM3 node.
# The AnyGrasp nodes start their own env (envs/anygrasp) through launchers/start_grasp_pipeline.py.
#   source <repo>/grasp/grasp_env.sh
# Sets up only this subsystem, so it can be started on its own. <repo>/global_env.sh sources all four.
# git finds the repo from this file's folder, and stops outside a git clone instead of guessing.
GAPPLER_REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)" || return 1
source "$GAPPLER_REPO/shared/base_envs/ros_humble_and_helper.sh" || return 1
if [ ! -f "$GAPPLER_REPO/install/local_setup.bash" ]; then
  echo "grasp_env.sh: no install/ in $GAPPLER_REPO. Run ./build.sh first." >&2
  return 1
fi
source "$GAPPLER_REPO/install/local_setup.bash"
source "$GAPPLER_REPO/shared/base_envs/uv_venv.sh" || return 1
