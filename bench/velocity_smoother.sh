#!/usr/bin/env bash
# T3.4 software only: private commands terminate at a recording subscriber.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ "${BENCH_DOMAIN:-127}" = 127 ] || { echo "REFUSED: T3.4 uses fixed domain 127"; exit 1; }
[ -f /opt/ros/humble/setup.bash ] || { echo "SKIP: no ROS 2 Humble here"; exit 3; }
export ROS_DOMAIN_ID=127 ROS_LOCALHOST_ONLY=1 PYTHONUNBUFFERED=1
set +u; source /opt/ros/humble/setup.bash; set -u
cd "$REPO"
python3 bench/t34_guard.py || exit 1
mkdir -p log
timeout --signal=INT --kill-after=10 120 python3 bench/nodes/test_velocity_smoother.py --teleop "$@"
