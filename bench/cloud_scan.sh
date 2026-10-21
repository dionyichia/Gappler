#!/usr/bin/env bash
# Synthetic clouds only: no sensor, base, arm, SLAM or Nav2 controller.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ "${BENCH_DOMAIN:-127}" = 127 ] || { echo "REFUSED: cloud/scan bench uses domain 127"; exit 1; }
[ -f /opt/ros/humble/setup.bash ] || { echo "SKIP: no ROS 2 Humble here"; exit 3; }
export ROS_DOMAIN_ID=127 ROS_LOCALHOST_ONLY=1 PYTHONUNBUFFERED=1
export PYTHONPATH="$REPO/shared${PYTHONPATH:+:$PYTHONPATH}"
set +u; source /opt/ros/humble/setup.bash; set -u
cd "$REPO"
python3 bench/t34_guard.py || exit 1
mkdir -p log
# Two owned groups can each take up to nine seconds to escalate; allow cleanup
# to finish before timeout kills the supervisor (children use separate sessions).
timeout --signal=INT --kill-after=30 90 python3 bench/nodes/test_cloud_scan_pipeline.py
