#!/usr/bin/env bash
# L4 -- replay recorded wrist-camera frames through SAM 3 and AnyGrasp (PROJECT_PLAN T0.12).
# Plays a bag made by grasp/tools/record_wrist_camera.sh, runs sam3_ros_node and
# anygrasp_detection_node on it, and plays the state machine's part by publishing
# /pipeline_state. No camera, no arm, no state machine: nothing can move.
#
#   ./bench/anygrasp_replay.sh      needs ./build.sh (grasp_interfaces), .venv (SAM 3),
#                                   grasp/anygrasp_venv/.venv, the weights, and a recording
#
# Env: WRIST_CAMERA_BAG (default assets/recordings/wrist_camera), BENCH_DOMAIN (default 77).
# Isolation: private ROS channel + localhost only.
# Exit: 0 pass (expected-fails allowed), 1 fail or refused, 3 SKIPPED -- never a pass.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="${BENCH_DOMAIN:-77}"
export WRIST_CAMERA_BAG="${WRIST_CAMERA_BAG:-$REPO/assets/recordings/wrist_camera}"

skip() { echo "SKIP: $*"; exit 3; }
[ -f /opt/ros/humble/setup.bash ] || skip "no ROS 2 Humble here"
[ -f "$REPO/install/setup.bash" ] || skip "no $REPO/install -- run ./build.sh first"
[ -f "$WRIST_CAMERA_BAG/metadata.yaml" ] || skip "no recording at $WRIST_CAMERA_BAG -- run grasp/tools/record_wrist_camera.sh"
[ -x "$REPO/.venv/bin/python" ] || skip "no .venv -- run uv sync"
[ -x "$REPO/grasp/anygrasp_venv/.venv/bin/python" ] || skip "no grasp/anygrasp_venv/.venv -- run ./grasp/anygrasp_venv/build_anygrasp_venv.sh"
[ -f "$REPO/grasp/anygrasp_node/log/checkpoint_detection.tar" ] || skip "AnyGrasp checkpoint missing (docs/ASSETS.md)"
[ -f "$REPO/aria/aria_app/models/sam3/sam3.pt" ] || skip "SAM 3 weights missing (docs/ASSETS.md)"
export ROS_DOMAIN_ID="$DOMAIN" ROS_LOCALHOST_ONLY=1 PYTHONUNBUFFERED=1
# the grasp subsystem's own env: ROS, install/, shared/ (gappler_common) and .venv
set +u; source "$REPO/grasp/grasp_env.sh" || { echo "FAIL: grasp/grasp_env.sh did not load"; exit 1; }; set -u
cd "$REPO"; mkdir -p log
export BENCH_REPLAY_LOG="log/bench_anygrasp_replay_$(date +%F_%H%M).txt"

# ---- guards: every one must hold before a node is started --------------------
refuse() { echo "REFUSED: $*"; exit 1; }
[ "$DOMAIN" != "0" ] || refuse "ROS_DOMAIN_ID 0 is the default channel the real robot uses"
busy="$(timeout 15 ros2 topic list --no-daemon --include-hidden-topics 2>/dev/null \
        | grep -vE '^/(parameter_events|rosout)$' || true)"
[ -z "$busy" ] || refuse "ROS channel $DOMAIN is not empty: $(echo $busy | head -c 200)"
echo "guards ok: channel $DOMAIN empty (hidden topics included), localhost only"

timeout 600 python3 "$REPO/bench/nodes/test_anygrasp_replay.py"; rc=$?
echo "node output: $BENCH_REPLAY_LOG"
exit $rc
