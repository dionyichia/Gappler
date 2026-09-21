#!/usr/bin/env bash
# The whole bench, one level at a time. Each level only runs if this machine can
# run it, and a level that cannot run is reported as SKIPPED, never as a pass.
#
#   L0  Static checks    code parses, imports and launch names resolve   any machine
#   L1  Contracts        no topic, frame or param name moved             any machine
#   L2  Lab box check    preflight: can this machine run L3-L4?          any machine
#   L3  Build            colcon build, arm and nav workspaces            needs ROS 2 Humble
#   L4  Simulation       simulated arm, mock Nav2, e-stop, AnyGrasp env  needs ROS + L3
#   L5  Robot check      preflight --hardware: is the robot there?      the lab box
#   L6  Hardware         the real arm test. Never run by this script     a person at the robot
#
#   ./bench/run.sh              every level this machine can run
#   ./bench/run.sh quick        L0-L2 only (skips the ~30 min build on the lab box)
#   ./bench/run.sh preflight    L2 only
#   ./bench/run.sh robot        L5 only (run this at the robot before an L6 test)
#   ./bench/run.sh report       contract inventory + orphan analysis
#
# Exit 0 when every level that ran passed. Skipped levels do not fail the run.
# L5 and L6 are not needed to merge: an unplugged arm makes L5 SKIPPED, not FAIL.
# Nothing here commands the arm -- see bench/preflight.py SAFETY.
set -uo pipefail
cd "$(dirname "$0")/.."

mode="${1:-all}"
case "$mode" in
  report)    exec python3 bench/contracts.py report ;;
  preflight) exec python3 bench/preflight.py ;;
  robot)     exec python3 bench/preflight.py --hardware ;;
  all|quick) ;;
  *) echo "usage: $0 [quick|preflight|robot|report]"; exit 2 ;;
esac

# In GitHub Actions, fold each level's output so the log reads as a list of levels.
gh=${GITHUB_ACTIONS:-}
open()  { if [ -n "$gh" ]; then echo "::group::$1"; else printf '\n######## %s ########\n' "$1"; fi; }
close() { [ -n "$gh" ] && echo "::endgroup::"; return 0; }

rows=()      # "level|name|status|note" for the summary
failed=0
row() { rows+=("$1|$2|$3|$4"); [ "$3" = FAIL ] && failed=1; return 0; }

# Run one script, map its exit code: 0 PASS, 3 SKIPPED, anything else FAIL.
# The level's own output goes to stderr so that $(step ...) captures only the status word.
step() {
  local label="$1"; shift
  { open "$label"; "$@"; } >&2; local rc=$?; close >&2
  case $rc in 0) echo PASS ;; 3) echo SKIPPED ;; *) echo FAIL ;; esac
}

s=$(step "L0  Static checks" python3 bench/static.py)
row L0 "Static checks" "$s" ""

s=$(step "L1  Contracts" python3 bench/contracts.py check)
row L1 "Contracts" "$s" ""

s=$(step "L2  Lab box check (preflight)" python3 bench/preflight.py)
# ponytail: "lab box" = ROS 2 Humble installed, the same test every L3-L4 script makes.
if [ -f /opt/ros/humble/setup.bash ]; then lab=1; note="ROS 2 Humble found, L3-L4 will run"
else lab=0; note="no ROS 2 Humble, so not the lab box. L3-L4 skipped"; fi
row L2 "Lab box check" "$s" "$note"

if [ "$mode" = quick ]; then
  row L3 "Build" SKIPPED "quick mode"
  row L4 "Simulation" SKIPPED "quick mode"
elif [ $lab = 0 ]; then
  row L3 "Build" SKIPPED "needs the lab box (see L2)"
  row L4 "Simulation" SKIPPED "needs the lab box (see L2)"
else
  arm=$(step "L3  Build: arm workspace" ./bench/build.sh arm)
  row L3 "Build: arm" "$arm" ""
  s=$(step "L3  Build: nav workspace" ./bench/build.sh nav)
  row L3 "Build: nav" "$s" ""
  if [ "$arm" != PASS ]; then
    row L4 "Simulation" SKIPPED "arm build did not pass (see L3)"
  else
    for t in sim_moveit estop_delivery state_machine_sim nav_nodes anygrasp_env; do
      s=$(step "L4  Simulation: $t" ./bench/$t.sh)
      row L4 "Sim: $t" "$s" ""
    done
  fi
fi
# L5 gates L6 the way L2 gates L3-L4. No arm on the network: SKIPPED, not FAIL.
if [ "$mode" = quick ]; then
  s=SKIPPED; row L5 "Robot check" SKIPPED "quick mode"
else
  s=$(step "L5  Robot check (preflight --hardware)" python3 bench/preflight.py --hardware)
  case $s in
    PASS)    row L5 "Robot check" PASS "arm, camera, LiDAR and glasses all answer" ;;
    SKIPPED) if [ $lab = 0 ]; then note="needs the lab box (see L2)"
             else note="the arm does not answer. Not needed to merge"; fi
             row L5 "Robot check" SKIPPED "$note" ;;
    *)       row L5 "Robot check" FAIL "the arm answers but something else is missing (see L5)" ;;
  esac
fi
if [ "$s" = PASS ]; then
  row L6 "Hardware" "NOT RUN" "robot ready. Needs a person with the e-stop, never automated"
else
  row L6 "Hardware" SKIPPED "L5 did not pass. Not needed to merge"
fi

echo
echo "======================================================================"
echo "  BENCH SUMMARY"
echo "----------------------------------------------------------------------"
for r in "${rows[@]}"; do
  IFS='|' read -r l n st note <<<"$r"
  printf "  %-3s %-26s %-8s %s\n" "$l" "$n" "$st" "$note"
done
echo "----------------------------------------------------------------------"
[ $failed = 0 ] && echo "  RESULT: PASS (every level that ran passed)" \
                || echo "  RESULT: FAIL (open the failing level's output above)"
echo "======================================================================"
echo "A green bench means no contract moved and the code is consistent. It does"
echo "NOT mean the robot works. L6 needs a human with the e-stop."

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Bench: $([ $failed = 0 ] && echo PASS || echo FAIL)"
    echo; echo "| Level | Check | Result | Note |"; echo "|---|---|---|---|"
    for r in "${rows[@]}"; do IFS='|' read -r l n st note <<<"$r"; echo "| $l | $n | $st | $note |"; done
    echo; echo "A green bench does not mean the robot works. L6 (hardware) is never run by CI."
  } >>"$GITHUB_STEP_SUMMARY"
fi

[ $failed = 0 ]
