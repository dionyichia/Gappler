#!/usr/bin/env bash
# Record the wrist camera to a ROS bag, so perception can be replayed without the arm (T0.12).
# Starts the RealSense driver for the wrist D435i only, records colour, aligned depth and their
# camera info, then stops the driver. Nothing else is started.
#
#   ./grasp/tools/record_wrist_camera.sh [SECONDS]     default 10
#
# Env, all optional:
#   WRIST_CAMERA_SERIAL  default 243222074878 (the wrist D435i). Pass it explicitly: with two
#                        cameras plugged in, the driver otherwise opens whichever it finds first.
#   WRIST_CAMERA_BAG     default assets/recordings/wrist_camera (gitignored). Must not exist yet.
#   ROS_DOMAIN_ID        default 79. Must be private and empty.
# Never passes initial_reset:=true. On 2026-09-14 it took this camera off the USB bus.
# Exit: 0 recorded, 1 failed or refused.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECS="${1:-10}"
SERIAL="${WRIST_CAMERA_SERIAL:-243222074878}"
BAG="${WRIST_CAMERA_BAG:-$REPO/assets/recordings/wrist_camera}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-79}" ROS_LOCALHOST_ONLY=1

refuse() { echo "REFUSED: $*"; exit 1; }
[ -f /opt/ros/humble/setup.bash ] || refuse "no ROS 2 Humble here"
set +u; source /opt/ros/humble/setup.bash; set -u
[ "$ROS_DOMAIN_ID" != "0" ] || refuse "ROS_DOMAIN_ID 0 is the default channel the real robot uses"
[ ! -e "$BAG" ] || refuse "$BAG already exists. Move it or set WRIST_CAMERA_BAG"
busy="$(timeout 15 ros2 topic list --no-daemon --include-hidden-topics 2>/dev/null \
        | grep -vE '^/(parameter_events|rosout)$' || true)"
[ -z "$busy" ] || refuse "ROS channel $ROS_DOMAIN_ID is not empty: $(echo $busy | head -c 200)"
# The box is shared: if anyone's camera driver is running, stop here and let a person decide.
others="$(pgrep -af 'realsense2_camera_node|rs_launch' | grep -v -e pgrep -e record_wrist_camera || true)"
[ -z "$others" ] || refuse "a RealSense driver is already running (someone may be using the cameras):
$others"
mkdir -p "$(dirname "$BAG")"
DRV_LOG="$BAG.driver.log"

# The leading _ makes the launch file read the serial as text, not a number.
setsid ros2 launch realsense2_camera rs_launch.py serial_no:="'_$SERIAL'" align_depth.enable:=true \
  rgb_camera.color_profile:=640x480x15 depth_module.depth_profile:=640x480x15 \
  >"$DRV_LOG" 2>&1 </dev/null &
PG=$!
# Stop only the driver's own process group, never other people's camera processes.
cleanup() { kill -INT -"$PG" 2>/dev/null; sleep 4; kill -KILL -"$PG" 2>/dev/null; }
trap cleanup EXIT

for _ in $(seq 1 30); do
  grep -aq "RealSense Node Is Up" "$DRV_LOG" && break
  kill -0 "$PG" 2>/dev/null || { echo "FAIL: driver exited. Tail of $DRV_LOG:"; tail -20 "$DRV_LOG"; exit 1; }
  sleep 1
done
grep -aq "RealSense Node Is Up" "$DRV_LOG" || { echo "FAIL: driver not up in 30 s, see $DRV_LOG"; exit 1; }
grep -aq "serial number $SERIAL was found" "$DRV_LOG" || { echo "FAIL: camera $SERIAL not found, see $DRV_LOG"; exit 1; }
sleep 3   # let both streams settle before recording
echo "driver up on camera $SERIAL, recording $SECS s to $BAG"

timeout -s INT "$SECS" ros2 bag record -o "$BAG" \
  /camera/camera/color/image_raw /camera/camera/color/camera_info \
  /camera/camera/aligned_depth_to_color/image_raw /camera/camera/aligned_depth_to_color/camera_info \
  >/dev/null 2>&1
sleep 2
info="$(ros2 bag info "$BAG" 2>&1)" || { echo "FAIL: no bag written"; echo "$info"; exit 1; }
echo "$info"
for t in color/image_raw aligned_depth_to_color/image_raw color/camera_info; do
  n="$(echo "$info" | grep "/camera/camera/$t " | sed -E 's/.*Count: ([0-9]+).*/\1/')"
  [ "${n:-0}" -gt 0 ] || { echo "FAIL: no messages on /camera/camera/$t"; exit 1; }
done
echo "RECORDED: $BAG"
