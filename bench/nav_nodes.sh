#!/usr/bin/env bash
# Tier 3 -- the navigation nodes against synthetic inputs (TESTBENCH_PLAN W7).
# object_approach_node, goal_reached_publisher, goto_glasses, qos_relay and
# pose_publisher, each started fresh from Navigation_Module/src/robot_slam/scripts/.
# Nothing can drive: no Nav2 and no base driver exist on the private channel;
# the test's mock navigate_to_pose server only records goals.
#
#   ./bench/nav_nodes.sh        needs ROS 2 Humble + nav2_msgs; not the nav build
#
# Isolation: private ROS channel (ROS_DOMAIN_ID, default 77) + localhost only.
# Exit: 0 pass (expected-fails allowed), 1 fail or refused, 3 SKIPPED -- never a pass.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="${BENCH_DOMAIN:-77}"

[ -f /opt/ros/humble/setup.bash ] || { echo "SKIP: no ROS 2 Humble here"; exit 3; }
export ROS_DOMAIN_ID="$DOMAIN" ROS_LOCALHOST_ONLY=1 PYTHONUNBUFFERED=1
set +u; source /opt/ros/humble/setup.bash; set -u
cd "$REPO"; mkdir -p log
export BENCH_NAV_LOG="log/bench_nav_nodes_$(date +%F_%H%M).txt"

# ---- guards: every one must hold before a node is started --------------------
refuse() { echo "REFUSED: $*"; exit 1; }
[ "$DOMAIN" != "0" ] || refuse "ROS_DOMAIN_ID 0 is the default channel the real robot uses"
# hidden topics too: a live navigate_to_pose server shows only as /navigate_to_pose/_action/*
busy="$(timeout 15 ros2 topic list --no-daemon --include-hidden-topics 2>/dev/null \
        | grep -vE '^/(parameter_events|rosout)$' || true)"
[ -z "$busy" ] || refuse "ROS channel $DOMAIN is not empty: $(echo $busy | head -c 200)"
echo "guards ok: channel $DOMAIN empty (hidden topics included), localhost only"

timeout 600 python3 "$REPO/bench/nodes/test_nav_nodes.py"; rc=$?
echo "node output: $BENCH_NAV_LOG"
exit $rc
