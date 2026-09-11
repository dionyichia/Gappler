#!/usr/bin/env bash
# Tier 3 -- MoveIt against a SIMULATED arm. The arm here is ros2_control's
# mock_components/GenericSystem: joint positions exist only in memory.
# rm_driver is never started, and the script refuses to run if one exists.
#
#   ./bench/sim_moveit.sh        needs ./bench/build.sh to have passed
#
# Isolation: private ROS channel (ROS_DOMAIN_ID, default 77) + localhost only.
# Exit: 0 pass, 1 fail or refused, 3 SKIPPED (no build / no ROS -- never a pass).
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="${BENCH_DOMAIN:-77}"
CFG=rm_65_w_gripper_config

[ -f /opt/ros/humble/setup.bash ] || { echo "SKIP: no ROS 2 Humble here"; exit 3; }
[ -f "$REPO/install/setup.bash" ] || { echo "SKIP: no $REPO/install -- run ./bench/build.sh first"; exit 3; }
export ROS_DOMAIN_ID="$DOMAIN" ROS_LOCALHOST_ONLY=1
set +u; source /opt/ros/humble/setup.bash; source "$REPO/install/setup.bash"; set -u
cd "$REPO"; mkdir -p log
LOG="log/bench_sim_moveit_$(date +%F_%H%M).txt"

# ---- guards: every one must hold before anything is launched ----------------
refuse() { echo "REFUSED: $*"; exit 1; }
share="$(ros2 pkg prefix "$CFG" 2>/dev/null)/share/$CFG"
[ -d "$share" ] || refuse "$CFG is not in $REPO/install"
grep -q "mock_components/GenericSystem" "$share/config/rm_65_with_gripper.ros2_control.xacro" \
  || refuse "installed ros2_control config is not mock_components -- this might drive real hardware"
grep -rqs "rm_driver" "$share/launch/demo.launch.py" && refuse "demo.launch.py mentions rm_driver"
pgrep -af "rm_driver" | grep -v -e pgrep -e sim_moveit >/dev/null \
  && refuse "an rm_driver process is running on this machine: $(pgrep -af rm_driver | head -1)"
busy="$(timeout 15 ros2 topic list --no-daemon 2>/dev/null | grep -vE '^/(parameter_events|rosout)$' || true)"
[ -z "$busy" ] || refuse "ROS channel $DOMAIN is not empty: $(echo $busy | head -c 200)"
echo "guards ok: mock_components, no rm_driver, channel $DOMAIN empty, localhost only"

# ---- launch the simulated arm, headless -------------------------------------
setsid ros2 launch "$CFG" demo.launch.py use_rviz:=false >"$LOG" 2>&1 &
PG=$!
cleanup() { kill -INT -"$PG" 2>/dev/null; sleep 4; kill -KILL -"$PG" 2>/dev/null; }
trap cleanup EXIT

for _ in $(seq 1 90); do
  grep -q "You can start planning now" "$LOG" && break
  kill -0 "$PG" 2>/dev/null || { echo "FAIL: launch exited early -- tail of $LOG:"; tail -20 "$LOG"; exit 1; }
  sleep 1
done
grep -q "You can start planning now" "$LOG" || { echo "FAIL: move_group not ready in 90 s -- see $LOG"; exit 1; }
echo "move_group ready (simulated arm)"

# rm_driver must not have appeared as a side effect of the launch
timeout 10 ros2 topic list --no-daemon 2>/dev/null | grep -q "^/rm_driver" \
  && { echo "FAIL: /rm_driver topics appeared -- stopping"; exit 1; }

timeout 180 python3 "$REPO/bench/nodes/test_sim_moveit.py"; rc=$?
echo "launch log: $LOG"
exit $rc
