# Shared services: programs every subsystem calls over ROS, starting with the segmentation
# service (T2.1). Needs the install/ overlay (segmentation_interfaces) and the project .venv (SAM 3).
#   source <repo>/shared_services/shared_services_env.sh
# Sets up only this folder, so the services can be started on their own. <repo>/global_env.sh
# sources it with the subsystems.
# git finds the repo from this file's folder, and stops outside a git clone instead of guessing.
GAPPLER_REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)" || return 1
source "$GAPPLER_REPO/shared/base_envs/ros_humble_and_helper.sh" || return 1
if [ ! -f "$GAPPLER_REPO/install/local_setup.bash" ]; then
  echo "shared_services_env.sh: no install/ in $GAPPLER_REPO. Run ./build.sh first." >&2
  return 1
fi
source "$GAPPLER_REPO/install/local_setup.bash"
source "$GAPPLER_REPO/shared/base_envs/uv_venv.sh" || return 1
# The SAM 3 wrapper still lives in aria (aria/aria_app/services/object_recognition/sam3_model.py).
# Drop this line if it moves into shared_services/segmentation/.
case ":$PYTHONPATH:" in *":$GAPPLER_REPO/aria/aria_app:"*) ;; *) export PYTHONPATH="$GAPPLER_REPO/aria/aria_app:$PYTHONPATH" ;; esac
