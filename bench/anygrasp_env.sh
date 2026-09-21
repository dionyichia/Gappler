#!/usr/bin/env bash
# W5 -- can a Python environment run AnyGrasp? Imports each dependency on its own, then runs
# the SDK's detection demo on the SDK's example frame with our licence + checkpoint.
# GPU inference only: no ROS, no robot, nothing published.
#
#   ./bench/anygrasp_env.sh [PYTHON]   default: first of envs/anygrasp/.venv, .venv
#   Build envs/anygrasp/.venv with ./envs/anygrasp/build.sh
#
# Exit: 0 pass, 1 fail, 3 SKIPPED (no interpreter / no checkpoint -- never a pass).
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO/bench/nodes/probe_anygrasp_env.py" "$@"
