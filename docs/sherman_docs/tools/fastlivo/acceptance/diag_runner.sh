#!/usr/bin/env bash
# Phase 3 diagnostics: repeats, odometry-trusting map, localization with every scan processed. Box only; gated on the pre-check.
set -u
OUT=${1:?output directory}
PRECHECK=${PHASE3_PRECHECK:?path of t35e_replay_precheck.sh}
bash "$PRECHECK" > /dev/null 2>&1 || { echo "BLOCKED by the pre-check; nothing started."; exit 1; }
export ROS_DOMAIN_ID=${PHASE3_DOMAIN:-178} ROS_LOCALHOST_ONLY=1 ROS2CLI_NO_DAEMON=1 PYTHONUNBUFFERED=1
set +u; source /opt/ros/humble/setup.bash; source "$HOME/rcp-Gappler/install_nav/setup.bash"; set -u
export OPTION2_SRC=${OPTION2_SRC:?}
H=$(dirname "$0")/option2_offline_acceptance.py
R1=${RUN1:?run 1 directory (its A_recorded map is reused)}
MT0="--slam-param minimum_travel_distance=0.0 --slam-param minimum_travel_heading=0.0"
run() { echo "=== $*"; bash "$PRECHECK" > /dev/null 2>&1 || { echo "BLOCKED mid-run; stopping"; exit 1; }; python3 "$H" "$@" || echo "FAILED: $*"; }
mkdir -p "$OUT"
# 1. repeats of A (map and reload), recorded stamps
run map      "$OUT/A2/"                                   --stamp recorded
run map      "$OUT/A3/"                                   --stamp recorded
run localize "$OUT/A2/loc"                                --stamp recorded --guess 2.0 1.2 0
run localize "$OUT/A3/loc"                                --stamp recorded --guess 2.0 1.2 0
# 3. odometry-trusting map: scan matching and loop closing off, the poses are FAST-LIVO2's
run map      "$OUT/D1/"                                   --stamp recorded --slam-param use_scan_matching=false --slam-param do_loop_closing=false
run localize "$OUT/D1/loc"                                --stamp recorded --guess 2.0 1.2 0
# 5. localization variance alone (run 1's map A) and with every scan processed (minimum travel 0)
run localize "$OUT/A1_loc_def_r1"                         --stamp recorded --guess 2.0 1.2 0 --graph "$R1/A_recorded/map/session"
run localize "$OUT/A1_loc_def_r2"                         --stamp recorded --guess 2.0 1.2 0 --graph "$R1/A_recorded/map/session"
run localize "$OUT/A1_loc_mt0_r1"                         --stamp recorded --guess 2.0 1.2 0 --graph "$R1/A_recorded/map/session" $MT0
run localize "$OUT/A1_loc_mt0_r2"                         --stamp recorded --guess 2.0 1.2 0 --graph "$R1/A_recorded/map/session" $MT0
run localize "$OUT/A2_loc_mt0"                            --stamp recorded --guess 2.0 1.2 0 --graph "$OUT/A2/map/session" $MT0
run localize "$OUT/A3_loc_mt0"                            --stamp recorded --guess 2.0 1.2 0 --graph "$OUT/A3/map/session" $MT0
run localize "$OUT/D1_loc_mt0"                            --stamp recorded --guess 2.0 1.2 0 --graph "$OUT/D1/map/session" $MT0
echo "=== done"
