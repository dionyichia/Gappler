#!/usr/bin/env bash
# Phase 3 offline acceptance, five sessions in order. Box only. Isolated domain, localhost only. No sudo, no hardware.
set -u
OUT=${1:?output directory}
export ROS_DOMAIN_ID=${PHASE3_DOMAIN:-178} ROS_LOCALHOST_ONLY=1 ROS2CLI_NO_DAEMON=1 PYTHONUNBUFFERED=1
source /opt/ros/humble/setup.bash; source "$HOME/rcp-Gappler/install_nav/setup.bash"
export OPTION2_SRC=${OPTION2_SRC:?directory holding nav/robot_slam of this branch}
H=$(dirname "$0")/option2_offline_acceptance.py
mkdir -p "$OUT"
run() { echo "=== $*"; python3 "$H" "$@" || echo "FAILED: $*"; }
run map      "$OUT/A_recorded/" --stamp recorded
run map      "$OUT/B_scanend/"  --stamp scanend
run scanonly "$OUT/C_scanonly/"
run localize "$OUT/A_recorded/loc" --stamp recorded --guess 2.0 1.2 0
run localize "$OUT/B_scanend/loc"  --stamp scanend  --guess 2.0 1.2 0
echo "=== done"
