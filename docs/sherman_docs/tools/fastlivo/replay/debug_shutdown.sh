#!/usr/bin/env bash
# Interactive, zero-input republisher shutdown probe; no mapper or recording.
set -eo pipefail
REPO="$HOME/rcp-Gappler"
[[ "$(id -un)" == rcp2026 && -d "$REPO/log" && -t 0 ]] || {
  echo 'Run in your interactive lab SSH terminal as rcp2026.' >&2; exit 1;
}
exec 9>>"$REPO/log/software-build.lock"
flock -n 9 || { echo 'Shared build lock is held; coordinate first.' >&2; exit 1; }
[[ ! -e "$REPO/log/software-build.lock.custody-unresolved" ]] || {
  echo 'Custody is unresolved; stop and coordinate.' >&2; exit 1;
}
status=0
pgrep -af 'Runner[.]Worker|bench/run[.]sh|(^|/|[[:space:]])colcon([[:space:]]|$)|ros2[[:space:]]+launch|fastlivo_mapping|image_transport/republish|rm_driver|xnode_vehicle' || status=$?
[[ "$status" == 1 ]] || { echo 'Process conflict or failed inspection; stopping.' >&2; exit 1; }
sudo -v
running=$(sudo docker ps --format '{{.Names}}')
[[ -z "$running" ]] || { printf 'Running containers; coordinate first:\n%s\n' "$running" >&2; exit 1; }
NAME="t35-shutdown-debug-$(date -u +%Y%m%dT%H%M%SZ)-$$"
printf 'Retained diagnostic container: %s\n' "$NAME"
echo 'The program launches automatically. After five seconds, press Ctrl+C once.'
echo 'At (gdb), type signal SIGINT; on SIGSEGV, type thread apply all bt full.'
echo 'Keep this terminal connected; use quit when finished.'
sudo docker run -it --pull=never --name "$NAME" \
  --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true --user 10001:10001 \
  --workdir /tmp --memory 2g --memory-swap 2g --cpus 1 --pids-limit 256 \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  --env HOME=/tmp --env ROS_LOG_DIR=/tmp/ros-log \
  --env ROS_DOMAIN_ID=173 --env ROS_LOCALHOST_ONLY=1 \
  --entrypoint /bin/bash t35-fastlivo-debug:shutdown \
  --noprofile --norc -c '
    set -e
    source /opt/ros/humble/setup.bash
    exec /usr/bin/gdb -q \
      -ex "set pagination off" \
      -ex "set debuginfod enabled off" \
      -ex "set disable-randomization off" \
      -ex "run" \
      --args /opt/ros/humble/lib/image_transport/republish \
      compressed raw --ros-args \
      -r __node:=t35_shutdown_probe \
      -r in/compressed:=/t35_shutdown_probe/unused/compressed \
      -r out:=/t35_shutdown_probe/raw -p use_sim_time:=true
  '
