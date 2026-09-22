# Grasp subsystem: the install/ overlay (shared with arm), and the project .venv for the SAM3 node.
# AnyGrasp has its own venv, grasp/anygrasp_venv/.venv, built below on first use. (The launcher
# still starts AnyGrasp through a conda env until T1.10 switches it over.)
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
# AnyGrasp's venv needs a CUDA compile (MinkowskiEngine, pointnet2), about 20 min. Built the first
# time it is missing, and only where it can be: a machine with nvcc and the project .venv. Elsewhere
# (a laptop without CUDA) it is skipped quietly. A failed build only warns, so the rest still sets up.
if [ ! -x "$GAPPLER_REPO/grasp/anygrasp_venv/.venv/bin/python" ] \
   && [ -x "$GAPPLER_REPO/.venv/bin/python" ] \
   && { command -v nvcc >/dev/null || [ -x "${CUDA_HOME:-/usr/local/cuda-12.8}/bin/nvcc" ]; }; then
  echo "grasp_env.sh: no AnyGrasp venv, building it now (about 20 min, first time only)." >&2
  "$GAPPLER_REPO/grasp/anygrasp_venv/build_anygrasp_venv.sh" \
    || echo "grasp_env.sh: AnyGrasp venv build failed, see above. The rest of grasp is set up." >&2
fi
