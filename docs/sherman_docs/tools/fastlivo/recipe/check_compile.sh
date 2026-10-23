#!/usr/bin/env bash
# Loader/package-discovery checks only: never execute a ROS node.
set -eo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
IMAGE="${T35_BUILD_IMAGE:-t59-fast-livo2:experimental}"
sudo -v
LOGDIR=$(mktemp -d "$PWD/compile-logs.XXXXXX")
echo "Retaining container t59-fastlivo-compile-check and logs in $LOGDIR (also on failure)."
sudo docker run --name t59-fastlivo-compile-check --network none --read-only \
    --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 \
    --memory 8g --memory-swap 8g --cpus 2 \
    --tmpfs /tmp:rw,noexec,nosuid,size=256m \
    --env HOME=/tmp --env ROS_HOME=/tmp/ros --env ROS_LOG_DIR=/tmp/ros/log \
    --user user --entrypoint bash "$IMAGE" -o pipefail -c '
    set -e
    mkdir -p "$ROS_LOG_DIR"
    source /opt/ros/humble/setup.bash
    source /fast_livo_ws/install/setup.bash
    packages=$(ros2 pkg executables fast_livo)
    printf "%s\n" "$packages"
    printf "%s\n" "$packages" | grep -Fx "fast_livo fastlivo_mapping"
    binary="$(ros2 pkg prefix fast_livo)/lib/fast_livo/fastlivo_mapping"
    test -x "$binary"
    dependencies=$(ldd "$binary")
    printf "%s\n" "$dependencies"
    case "$dependencies" in *"not found"*) exit 1;; esac
    echo "Compile-only checks passed; no ROS nodes were started."
    ' 2>&1 | tee "$LOGDIR/compile-check.log"
