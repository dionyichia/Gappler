#!/usr/bin/env bash
# Tier 3 -- rm_mtc's grasp_state_machine against a SIMULATED arm (TESTBENCH_PLAN W2).
# The arm is ros2_control's mock_components: joint positions exist only in memory. rm_driver
# is never started; the gripper commands the state machine sends are only recorded.
#
#   ./bench/state_machine_sim.sh        needs ./bench/build.sh to have passed
#
# CLAUDE.md forbids launching grasp_state_machine; Dion allowed this one exception on
# 2026-09-11 for the simulated arm only, behind every guard below.
# Isolation: private ROS channel (ROS_DOMAIN_ID, default 77) + localhost only.
# Exit: 0 pass (expected-fails allowed), 1 fail or refused, 3 SKIPPED -- never a pass.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="${BENCH_DOMAIN:-77}"
CFG=rm_65_w_gripper_config

[ -f /opt/ros/humble/setup.bash ] || { echo "SKIP: no ROS 2 Humble here"; exit 3; }
[ -f "$REPO/install/setup.bash" ] || { echo "SKIP: no $REPO/install -- run ./bench/build.sh first"; exit 3; }
export ROS_DOMAIN_ID="$DOMAIN" ROS_LOCALHOST_ONLY=1
set +u; source /opt/ros/humble/setup.bash; source "$REPO/install/setup.bash"; set -u
cd "$REPO"; mkdir -p log
export BENCH_SM_LOG="log/bench_state_machine_$(date +%F_%H%M).txt"

# ---- guards: every one must hold before anything is launched ----------------
refuse() { echo "REFUSED: $*"; exit 1; }
[ "$DOMAIN" != "0" ] || refuse "ROS_DOMAIN_ID 0 is the default channel the real robot uses"
ros2 pkg prefix rm_mtc >/dev/null 2>&1 || refuse "rm_mtc is not in $REPO/install"
share="$(ros2 pkg prefix "$CFG" 2>/dev/null)/share/$CFG"
[ -d "$share" ] || refuse "$CFG is not in $REPO/install"
grep -q "mock_components/GenericSystem" "$share/config/rm_65_with_gripper.ros2_control.xacro" \
  || refuse "installed ros2_control config is not mock_components -- this might drive real hardware"
LAUNCH="$REPO/bench/nodes/sim_state_machine.launch.py"
# a quoted package name is how launch code starts a node; prose in comments is not
grep -qsE "[\"']rm_driver[\"']" "$LAUNCH" "$REPO/bench/nodes/sim_arm.urdf.xacro" && refuse "the bench launch references the rm_driver package"
n_ctl="$(xacro "$REPO/bench/nodes/sim_arm.urdf.xacro" initial_positions_file:="$share/config/initial_positions.yaml" 2>/dev/null | grep -c "mock_components/GenericSystem")"
[ "$n_ctl" = "1" ] || refuse "sim robot model has $n_ctl mock_components blocks, expected exactly 1"
pgrep -af "rm_driver" | grep -v -e pgrep -e state_machine_sim >/dev/null \
  && refuse "an rm_driver process is running on this machine: $(pgrep -af rm_driver | head -1)"
# Dion's point: the preflight network gates must show the arm is unreachable. preflight exits
# non-zero whenever any check fails (e.g. the unplugged port), so read its JSON, not its exit code.
netjson="$(python3 bench/preflight.py -g net --json 2>/dev/null || true)"
armcheck="$(printf '%s' "$netjson" | python3 -c '
import json, sys
cs = {c["name"]: c["status"] for c in json.load(sys.stdin)}
st = {k: cs.get(k, "MISSING") for k in ("arm-ping", "arm-port")}
print(" ".join(f"{k}={v}" for k, v in st.items()))
sys.exit(2 if "PASS" in st.values() else 3 if "MISSING" in st.values() else 0)' 2>/dev/null)"
case $? in
  0) ;;
  2) refuse "the real arm answers on the network ($armcheck) -- unplug it or power it off first" ;;
  3) refuse "preflight did not report both arm checks ($armcheck)" ;;
  *) refuse "could not read the preflight network checks" ;;
esac
busy="$(timeout 15 ros2 topic list --no-daemon 2>/dev/null | grep -vE '^/(parameter_events|rosout)$' || true)"
[ -z "$busy" ] || refuse "ROS channel $DOMAIN is not empty: $(echo $busy | head -c 200)"
echo "guards ok: mock_components, no rm_driver, arm unreachable ($armcheck), channel $DOMAIN empty, localhost only"

# ---- launch the simulated arm + state machine, headless ---------------------
setsid ros2 launch "$LAUNCH" use_rviz:=false >"$BENCH_SM_LOG" 2>&1 &
PG=$!
cleanup() { kill -INT -"$PG" 2>/dev/null; sleep 4; kill -KILL -"$PG" 2>/dev/null; }
trap cleanup EXIT

for _ in $(seq 1 120); do
  grep -q "You can start planning now" "$BENCH_SM_LOG" && break
  kill -0 "$PG" 2>/dev/null || { echo "FAIL: launch exited early -- tail of $BENCH_SM_LOG:"; tail -20 "$BENCH_SM_LOG"; exit 1; }
  sleep 1
done
grep -q "You can start planning now" "$BENCH_SM_LOG" || { echo "FAIL: move_group not ready in 120 s -- see $BENCH_SM_LOG"; exit 1; }
echo "move_group ready (simulated arm); state machine launched"

# the real driver must not have appeared as a side effect (its topics exist -- the state
# machine publishes to them -- but no rm_driver node may be listening)
timeout 10 ros2 node list --no-daemon 2>/dev/null | grep -qi "rm_driver" \
  && { echo "FAIL: an rm_driver node appeared -- stopping"; exit 1; }

timeout 900 python3 "$REPO/bench/nodes/test_state_machine_sim.py"; rc=$?
echo "launch log: $BENCH_SM_LOG"
exit $rc
