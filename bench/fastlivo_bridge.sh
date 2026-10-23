#!/usr/bin/env bash
# Option 2 runtime check: bridge and converter on the recorded handdriven1 odometry and LiDAR. No sensor, base, arm, mapper or Docker.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ "${BENCH_DOMAIN:-127}" = 127 ] || { echo "REFUSED: this bench uses domain 127"; exit 1; }
[ -f /opt/ros/humble/setup.bash ] || { echo "SKIP: no ROS 2 Humble here"; exit 3; }
export ROS_DOMAIN_ID=127 ROS_LOCALHOST_ONLY=1 PYTHONUNBUFFERED=1
export PYTHONPATH="$REPO/shared${PYTHONPATH:+:$PYTHONPATH}"
set +u; source /opt/ros/humble/setup.bash
# the converter needs the CustomMsg type from the nav overlay (livox_ros_driver2)
NAV_OVERLAY="${BENCH_NAV_OVERLAY:-$REPO/install_nav/setup.bash}"
[ -f "$NAV_OVERLAY" ] && source "$NAV_OVERLAY"
set -u
cd "$REPO"
python3 bench/t34_guard.py || exit 1
mkdir -p log
timeout --signal=INT --kill-after=30 120 python3 bench/nodes/test_fastlivo_bridge.py
