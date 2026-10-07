#!/usr/bin/env bash
# Synthetic scan/TF only: no hardware drivers, Nav2 controller or wheel commands.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ "${BENCH_DOMAIN:-127}" = 127 ] || { echo "REFUSED: SLAM test uses domain 127"; exit 1; }
[ -f /opt/ros/humble/setup.bash ] || { echo "SKIP: no ROS 2 Humble here"; exit 3; }
export ROS_DOMAIN_ID=127 ROS_LOCALHOST_ONLY=1 PYTHONUNBUFFERED=1
export PYTHONPATH="$REPO/shared${PYTHONPATH:+:$PYTHONPATH}"
set +u; source /opt/ros/humble/setup.bash; set -u
cd "$REPO"
python3 bench/t34_guard.py || exit 1
mkdir -p log
timeout --signal=INT --kill-after=30 180 python3 bench/nodes/test_slam_persistence.py
