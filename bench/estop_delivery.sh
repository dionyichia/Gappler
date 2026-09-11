#!/usr/bin/env bash
# Tier 3 -- does ros2_robot_ws/src/estop.py actually deliver its stop message?
# CODE_AUDIT B2. Nothing here moves anything: rm_driver is never started, the
# channel is private, and the script refuses to run if an rm_driver exists.
#
#   ./bench/estop_delivery.sh        needs ./bench/build.sh (for rm_ros_interfaces)
#
# Isolation: private ROS channel (ROS_DOMAIN_ID, default 77) + localhost only.
# Exit: 0 pass (expected-fails allowed), 1 fail or refused, 3 SKIPPED -- never a pass.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="${BENCH_DOMAIN:-77}"

[ -f /opt/ros/humble/setup.bash ] || { echo "SKIP: no ROS 2 Humble here"; exit 3; }
[ -f "$REPO/install/setup.bash" ] || { echo "SKIP: no $REPO/install -- run ./bench/build.sh first"; exit 3; }
export ROS_DOMAIN_ID="$DOMAIN" ROS_LOCALHOST_ONLY=1
set +u; source /opt/ros/humble/setup.bash; source "$REPO/install/setup.bash"; set -u
cd "$REPO"; mkdir -p log
export BENCH_ESTOP_LOG="log/bench_estop_$(date +%F_%H%M).txt"

# ---- guards: every one must hold before estop.py is started -----------------
refuse() { echo "REFUSED: $*"; exit 1; }
[ "$DOMAIN" != "0" ] || refuse "ROS_DOMAIN_ID 0 is the default channel the real robot uses"
ros2 pkg prefix rm_ros_interfaces >/dev/null 2>&1 || refuse "rm_ros_interfaces is not in $REPO/install"
pgrep -af "rm_driver" | grep -v -e pgrep -e estop_delivery >/dev/null \
  && refuse "an rm_driver process is running on this machine: $(pgrep -af rm_driver | head -1)"
busy="$(timeout 15 ros2 topic list --no-daemon 2>/dev/null | grep -vE '^/(parameter_events|rosout)$' || true)"
[ -z "$busy" ] || refuse "ROS channel $DOMAIN is not empty: $(echo $busy | head -c 200)"
echo "guards ok: no rm_driver, channel $DOMAIN empty, localhost only"

timeout 240 python3 "$REPO/bench/nodes/test_estop_delivery.py"; rc=$?
echo "estop.py output: $BENCH_ESTOP_LOG"
exit $rc
