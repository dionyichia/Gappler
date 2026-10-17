#!/bin/bash
# T2.21 end-to-end on a recording: service + aria client + glasses replay with sound. The sound is
# the stitched commands.wav ("pick up the box" at 22, 46, 70 and 95 s, decision 9b), played on the
# recording's own microphone clock, so the word is stamped on the same clock as images and gaze.
# Private channel, nothing that moves. Stops only the process groups it started.
# Scratch folder: a copy of the repo in $S/repo (.venv, install, assets linked from the main
# clone), the recording and commands.wav in $S. Logs go to $S/e2e_t2.21_logs.
S="${T29_SCRATCH:-$HOME/dion_t2.9}"
REC=c2cbafe8-ebc9-4279-8782-8cdaeb81b99b
cd "$S/repo" || exit 1
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=88
source aria/aria_env.sh >/dev/null
L="$S/e2e_t2.21_logs"; rm -rf $L; mkdir -p $L
PG=()
start() { setsid "$@" & PG+=($!); }
start python -u shared_services/segmentation/segmentation_service.py > $L/service.log 2>&1
start python -u aria/aria_app/services/aria_segmentation_client/aria_segmentation_client.py > $L/client.log 2>&1
start ros2 topic echo /grasp/target segmentation_interfaces/msg/Target --no-arr > $L/target.log 2>&1
start ros2 topic echo /aria/audio/prompt_stamped segmentation_interfaces/msg/SpokenWord > $L/word.log 2>&1
start ros2 topic echo /aria/audio/prompt std_msgs/msg/String > $L/word_string.log 2>&1
start python -u aria/tools/replay_recording_to_glasses_topics.py "$S/$REC.vrs" --from-s 0 --to-s 118 --audio-wav "$S/$REC.commands.wav" > $L/replay.log 2>&1
stop() { for p in "${PG[@]}"; do kill -INT -$p 2>/dev/null; done; sleep 3; for p in "${PG[@]}"; do kill -KILL -$p 2>/dev/null; done; }
trap stop EXIT
# workers and Whisper load first (a minute or two), then 118 s of playback
for i in $(seq 400); do grep -q "^Done at\|stopped\|Error" $L/replay.log && break; sleep 1; done
sleep 5   # the last word's segmentation reply
