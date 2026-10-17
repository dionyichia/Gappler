#!/bin/bash
# T2.9 end-to-end on a recording: service + aria client + glasses replay, "box" said once per stop.
# Private channel, nothing that moves. Stops only the process groups it started.
# Scratch folder: a copy of the repo in $S/repo (.venv, install, assets linked from the main
# clone), the recording in $S. Logs go to $S/e2e_logs.
S="${T29_SCRATCH:-$HOME/dion_t2.9}"
cd "$S/repo" || exit 1
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=88
source aria/aria_env.sh >/dev/null
L="$S/e2e_logs"; rm -rf $L; mkdir -p $L
PG=()
start() { setsid "$@" & PG+=($!); }
start python -u shared_services/segmentation/segmentation_service.py > $L/service.log 2>&1
start python -u aria/aria_app/services/aria_segmentation_client/aria_segmentation_client.py > $L/client.log 2>&1
start ros2 topic echo /grasp/target segmentation_interfaces/msg/Target --no-arr > $L/target.log 2>&1
start ros2 topic hz /aria/eye_tracking/gaze_estimate > $L/gaze_hz.log 2>&1
start ros2 topic hz /aria/rgb_camera/undistorted > $L/image_hz.log 2>&1
start python -u aria/tools/replay_recording_to_glasses_topics.py "$S"/c2cbafe8-ebc9-4279-8782-8cdaeb81b99b.vrs --from-s 0 --to-s 118 > $L/replay.log 2>&1
stop() { for p in "${PG[@]}"; do kill -INT -$p 2>/dev/null; done; sleep 3; for p in "${PG[@]}"; do kill -KILL -$p 2>/dev/null; done; }
trap stop EXIT
for i in $(seq 120); do grep -q "Playing from" $L/replay.log && break; sleep 1; done
t0=$(date +%s.%N)
for at in 22 46 70 95; do
  while (( $(echo "$(date +%s.%N) - $t0 < $at" | bc) )); do sleep 0.2; done
  echo "[$(date +%T)] say box at ${at}s" | tee -a $L/said.log
  ros2 topic pub --once /aria/audio/prompt std_msgs/msg/String "data: box" > /dev/null
done
# let the replay finish, so stopping it does not cut it off mid-publish
for i in $(seq 40); do grep -q "^Done at" $L/replay.log && break; sleep 1; done
