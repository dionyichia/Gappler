#!/usr/bin/env bash
# T3.5d probe: run the tested mapper image on the host network. Starts no sensor driver.
# Needs T35_REPLAY_IMAGE, T35_MAPPER_CONFIG, T35_CAMERA_CONFIG and T35_PROBE_OUT. Operator-run only.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
IMAGE=${T35_REPLAY_IMAGE:?}
MAPPER_CONFIG=${T35_MAPPER_CONFIG:?}
CAMERA_CONFIG=${T35_CAMERA_CONFIG:?}
OUT=${T35_PROBE_OUT:?}
SIM_TIME=${T35_USE_SIM_TIME:-true}
mkdir -p "$OUT"/Log/result "$OUT"/Log/pcd "$OUT"/Log/image "$OUT"/Log/ref_cur_combine "$OUT"/ros "$OUT"/ros-log
sudo docker run --rm --name t35d-probe --network host --ipc host --user "$(id -u):$(id -g)" \
  --memory 8g --memory-swap 8g --cpus 2 --pids-limit 512 \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --env ROS_DOMAIN_ID=174 --env ROS_LOCALHOST_ONLY=1 --env ROS2CLI_NO_DAEMON=1 \
  --env HOME=/tmp --env ROS_HOME=/out/ros --env ROS_LOG_DIR=/out/ros-log \
  --env OMP_NUM_THREADS=2 --env OPENBLAS_NUM_THREADS=1 \
  --env "MAPPER_CONFIG=$MAPPER_CONFIG" --env "CAMERA_CONFIG=$CAMERA_CONFIG" --env "SIM_TIME=$SIM_TIME" \
  -v "$HERE/config:/cfg:ro" -v "$OUT/Log:/fast_livo_ws/src/fast_livo/Log" \
  -v "$OUT:/out" \
  --workdir /fast_livo_ws --entrypoint /bin/bash "$IMAGE" -c '
set -e
source /opt/ros/humble/setup.bash && source /fast_livo_ws/install/setup.bash
/opt/ros/humble/lib/demo_nodes_cpp/parameter_blackboard --ros-args -r __node:=parameter_blackboard \
  --params-file "/cfg/$CAMERA_CONFIG" -p use_sim_time:=$SIM_TIME >/out/camera.stdout.log 2>/out/camera.stderr.log &
BB=$!
sleep 4
/fast_livo_ws/install/fast_livo/lib/fast_livo/fastlivo_mapping --ros-args -r __node:=laserMapping \
  --params-file "/cfg/$MAPPER_CONFIG" -p use_sim_time:=$SIM_TIME >/out/mapper.stdout.log 2>/out/mapper.stderr.log &
MAP=$!
trap "kill -INT $MAP $BB 2>/dev/null; wait" INT TERM
echo "probe up: mapper pid $MAP, camera server pid $BB; Ctrl-C to stop"
wait $MAP
kill -INT $BB 2>/dev/null || true
wait
'
