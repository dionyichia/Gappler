#!/usr/bin/env bash
# L4 -- the segmentation service with the real SAM 3, on a frame of the recorded box video (T2.1).
# Starts shared_services/segmentation/segmentation_service.py and calls it: image only, image with
# depth and camera info, and an empty prompt. No camera, no arm: nothing can move.
#
#   ./bench/segmentation_service.sh   needs ./build.sh (segmentation_interfaces), .venv (SAM 3),
#                                     the SAM 3 weights, and the recording
#
# Env: WRIST_CAMERA_BAG (default assets/recordings/wrist_camera), BENCH_DOMAIN (default 77).
# Isolation: private ROS channel + localhost only.
# Exit: 0 pass, 1 fail or refused, 3 SKIPPED -- never a pass.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="${BENCH_DOMAIN:-77}"
export WRIST_CAMERA_BAG="${WRIST_CAMERA_BAG:-$REPO/assets/recordings/wrist_camera}"

skip() { echo "SKIP: $*"; exit 3; }
[ -f /opt/ros/humble/setup.bash ] || skip "no ROS 2 Humble here"
[ -f "$REPO/install/setup.bash" ] || skip "no $REPO/install -- run ./build.sh first"
[ -f "$WRIST_CAMERA_BAG/metadata.yaml" ] || skip "no recording at $WRIST_CAMERA_BAG -- run grasp/tools/record_wrist_camera.sh"
[ -x "$REPO/.venv/bin/python" ] || skip "no .venv -- run uv sync"
[ -f "${GAPPLER_SAM3_WEIGHTS:-$REPO/assets/models/sam3/sam3.pt}" ] || skip "SAM 3 weights missing (docs/ASSETS.md)"
export ROS_DOMAIN_ID="$DOMAIN" ROS_LOCALHOST_ONLY=1 PYTHONUNBUFFERED=1
set +u; source "$REPO/shared_services/shared_services_env.sh" || { echo "FAIL: shared_services_env.sh did not load"; exit 1; }; set -u
cd "$REPO"; mkdir -p log
export BENCH_SEG_LOG="log/bench_segmentation_service_$(date +%F_%H%M).txt"

# ---- guards: every one must hold before the service is started ----------------
refuse() { echo "REFUSED: $*"; exit 1; }
[ "$DOMAIN" != "0" ] || refuse "ROS_DOMAIN_ID 0 is the default channel the real robot uses"
busy="$(timeout 15 ros2 topic list --no-daemon --include-hidden-topics 2>/dev/null \
        | grep -vE '^/(parameter_events|rosout)$' || true)"
[ -z "$busy" ] || refuse "ROS channel $DOMAIN is not empty: $(echo $busy | head -c 200)"
echo "guards ok: channel $DOMAIN empty (hidden topics included), localhost only"

timeout 300 python "$REPO/bench/nodes/test_segmentation_service.py"; rc=$?
echo "service output: $BENCH_SEG_LOG"
exit $rc
