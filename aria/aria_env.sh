# Aria glasses subsystem: the project .venv, and aria/aria_app/ on PYTHONPATH.
#   source <repo>/aria/aria_env.sh
# Sets up only this subsystem, so it can be started on its own. <repo>/global_env.sh sources all four.
# git finds the repo from this file's folder, and stops outside a git clone instead of guessing.
GAPPLER_REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)" || return 1
source "$GAPPLER_REPO/shared/base_envs/ros_humble_and_helper.sh" || return 1
source "$GAPPLER_REPO/shared/base_envs/uv_venv.sh" || return 1
case ":$PYTHONPATH:" in *":$GAPPLER_REPO/aria/aria_app:"*) ;; *) export PYTHONPATH="$GAPPLER_REPO/aria/aria_app:$PYTHONPATH" ;; esac
