#!/usr/bin/env bash
# T3.5d probe: play the stationary02 bag from the host into the container mapper. Bag only, no hardware.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
BAG=${T35_REPLAY_BAG:?}
set +u
source /opt/ros/humble/setup.bash
source "$HOME/rcp-Gappler/install_nav/setup.bash"
set -u
export ROS_DOMAIN_ID=174 ROS_LOCALHOST_ONLY=1 ROS2CLI_NO_DAEMON=1
ros2 bag play "$BAG" --clock 100 --rate 0.25 --disable-keyboard-controls \
  --qos-profile-overrides-path "$HERE/playback_qos.yaml"
