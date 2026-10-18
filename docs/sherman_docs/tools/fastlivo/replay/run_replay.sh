#!/usr/bin/env bash
# User-run on the lab host only. No host ROS, downloads, retries, or deletion.
set -Eeuo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO=/home/rcp2026/rcp-Gappler
# Defaults are the reviewed public raw bag and its configs. Override the three
# for another reviewed recording (T3.5c used the staged t35b/t35c set). The bag
# and configs are staged bytes: this wrapper never writes or converts them.
BAG="${T35_REPLAY_BAG:-$REPO/log/t59-fastlivo/log/datasets/bright-screen-wall/Bright_Screen_Wall_raw}"
MAPPER_CONFIG="${T35_MAPPER_CONFIG:-bright_screen_wall.yaml}"
CAMERA_CONFIG="${T35_CAMERA_CONFIG:-camera_pinhole.yaml}"
SOURCE_COMMIT="${T35_SOURCE_COMMIT:-a09599a288c56b832114d7ad9e898248a4111d9e}"
# Override for sanitizer/debug images only; default is the reviewed build.
IMAGE="${T35_REPLAY_IMAGE:-t59-fast-livo2:experimental}"
# Passed into the container; ignored by non-instrumented binaries.
ASAN_OPTIONS_VALUE="${T35_ASAN_OPTIONS:-detect_leaks=0:halt_on_error=1:abort_on_error=1}"
# Sanitizer runs only: preload the runtime first so uninstrumented helpers
# (bag player, CLI tools) do not abort. Empty by default; harmless when unset.
LD_PRELOAD_VALUE="${T35_LD_PRELOAD:-}"
RATE="${T35_REPLAY_RATE:-0.25}"
DIAGNOSTIC=0
for name in "$MAPPER_CONFIG" "$CAMERA_CONFIG"; do
  [[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*\.yaml$ ]] \
    || { echo "REFUSED: config name must be a plain basename: $name" >&2; exit 1; }
done
if [[ "$#" -eq 1 && "$1" == '--diagnostic' ]]; then
  DIAGNOSTIC=1
elif [[ "$#" -ne 0 ]]; then
  echo 'Usage: bash run_replay.sh [--diagnostic]' >&2; exit 1
fi
if [[ "$DIAGNOSTIC" == 1 ]]; then
  echo 'PAUSED DIAGNOSTIC ONLY: capture all graph topics/package versions; never resume playback.'
fi
[[ $(id -u) != 0 && $(id -un) == rcp2026 && -d "$REPO/log" ]] || {
  echo 'REFUSED: run as ordinary rcp2026 on the lab host, not via sudo bash.' >&2; exit 1;
}
for tool in python3 flock timeout sudo; do command -v "$tool" >/dev/null; done
for file in replay.py replay_progress.py playback_qos.yaml verify_replay_container.py \
  config/$MAPPER_CONFIG config/$CAMERA_CONFIG; do
  [[ -r "$HERE/$file" ]] || { echo "Missing reviewed input: $HERE/$file" >&2; exit 1; }
done
[[ -r "$BAG/metadata.yaml" ]] || { echo "Missing converted bag: $BAG" >&2; exit 1; }
printf '%s\n' \
  'Coordinate shared-box custody with the lab team before continuing.' \
  'This reserves 2 CPUs / 8 GiB for up to 600 seconds. No other work will be stopped.' \
  'Confirm no conflicting build/replay/robot work and an agreed replay window.'
read -r -p 'Type CUSTODY AGREED to continue: ' answer </dev/tty
[[ "$answer" == 'CUSTODY AGREED' ]] || { echo 'Custody not confirmed.' >&2; exit 1; }
exec 9>>"$REPO/log/software-build.lock"
flock -n 9 || { echo 'REFUSED: software-build.lock already held; coordinate, do not stop its owner.' >&2; exit 1; }
HOLD="$REPO/log/software-build.lock.custody-unresolved"
[[ ! -e "$HOLD" ]] || { echo "REFUSED: unresolved custody hold: $HOLD; human verification required." >&2; exit 1; }
sudo -v

# Conservative read-only conflict gate. An empty scan is not physical custody proof.
check_conflicts() {
python3 - <<'PY'
import re
import subprocess
import sys
text = subprocess.check_output(["ps", "-eo", "pid,user,comm,args"], text=True)
pattern = re.compile(r"(?:^|[/\s])(?:colcon|cmake|ninja|make|gmake|cc1plus|cc1|nvcc|"
                     r"ros2|roscore|rosmaster|fastlivo_mapping|parameter_blackboard|"
                     r"livox_ros_driver2_node|rm_driver|xnode_comm|teleop_twist_keyboard|"
                     r"Runner\.Worker|bench/run\.sh|realsense[^/\s]*|xnode_vehicle[^/\s]*)(?:\s|$)")
conflicts = [line for line in text.splitlines()[1:] if pattern.search(line)]
if conflicts:
    print("REFUSED: possible shared-box conflicts (nothing stopped):", *conflicts, sep="\n", file=sys.stderr)
    sys.exit(1)
PY
running=$(timeout -k 5s 10s sudo -n docker ps --format '{{.ID}} {{.Names}} {{.Image}}')
[[ -z "$running" ]] || { printf 'REFUSED: running containers; coordinate first:\n%s\n' "$running" >&2; exit 1; }
}
check_conflicts

C="t59-replay-$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="$REPO/log/t59-fastlivo/replays/$C"
mkdir -p -- "$OUT"
created=0
started=0
unresolved=0
keeper_pid=0
log_pid=0
confirm_stopped() {
  # A failed inspect is UNKNOWN, never proof that a container stopped.
  timeout -k 5s 10s sudo -n docker inspect "$C" >"$OUT/container.state-unconfirmed.inspect.json" \
    2>"$OUT/state-check.stderr.log" || return 1
  python3 - "$OUT/container.state-unconfirmed.inspect.json" <<'PY'
import json, sys
with open(sys.argv[1]) as source:
    docs = json.load(source)
if len(docs) != 1:
    sys.exit(1)
state = docs[0]["State"]
sys.exit(0 if state["Running"] is False and state["Status"] in ("created", "exited")
         and not state.get("Restarting") and not state.get("Paused") else 1)
PY
}
mark_unresolved() {
  unresolved=1
  # No unlock/delete path: only a human may clear this after verifying custody.
  printf 'CRITICAL custody unresolved: %s; state is NOT final. Evidence: %s\n' "$C" "$OUT" \
    | tee "$OUT/custody-unresolved.txt" "$HOLD" >&2
  if (( keeper_pid == 0 )); then
    # Keep the existing kernel lock, not merely a marker. No Docker/ROS commands
    # run in this host helper. It exits only when a human clears the hold marker.
    python3 -c '
import fcntl, os, pathlib, signal, sys, time
os.fstat(9)
fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
os.setsid()
signal.signal(signal.SIGHUP, signal.SIG_IGN)
hold, ready = map(pathlib.Path, sys.argv[1:])
ready.write_text(str(os.getpid()) + "\n")
while hold.exists():
    time.sleep(1)
' "$HOLD" "$OUT/custody-lock-keeper.ready" </dev/null \
      >"$OUT/custody-lock-keeper.log" 2>&1 9>&9 &
    keeper_pid=$!
    printf '%s\n' "$keeper_pid" >"$OUT/custody-lock-keeper.pid"
    for (( attempt=0; attempt<20; attempt++ )); do
      [[ -s "$OUT/custody-lock-keeper.ready" ]] && break
      sleep 0.1
    done
    if [[ ! -s "$OUT/custody-lock-keeper.ready" ]]; then
      echo 'CRITICAL custody unresolved: lock-holder startup NOT confirmed; immediate human intervention required.' >&2
    else
      printf 'Custody lock retained by PID %s; clear %s ONLY after manually verifying stopped state.\n' \
        "$keeper_pid" "$HOLD" >&2
    fi
  fi
}
stop_owned() {
  # ONLY this run's exact container name is ever signalled; never enumerate targets.
  if ! timeout -k 5s 10s sudo -n docker kill --signal SIGINT "$C"; then
    echo "SIGINT request failed for $C; checking state before fallback." >&2
  fi
  if ! timeout -k 5s 20s sudo -n docker wait "$C" >"$OUT/interrupted.wait.log" 2>&1; then
    echo "Graceful wait failed for $C; inspecting before exact-name SIGKILL." >&2
  fi
  if confirm_stopped; then return 0; fi
  if ! timeout -k 5s 10s sudo -n docker kill --signal SIGKILL "$C"; then
    echo "SIGKILL request failed for $C; custody must be verified." >&2
  fi
  if ! timeout -k 5s 10s sudo -n docker wait "$C" >"$OUT/forced.wait.log" 2>&1; then
    echo "Forced-stop wait failed for $C." >&2
  fi
  if ! confirm_stopped; then
    mark_unresolved
    return 1
  fi
}
collect() {
  local status=$?
  trap - EXIT
  set +e
  if (( log_pid )); then
    # Only our bounded Docker log client; never a container or another operator.
    kill "$log_pid" 2>/dev/null
    wait "$log_pid"
  fi
  if (( created )); then
    if (( started && ! unresolved )) && ! confirm_stopped; then
      status=1
      stop_owned
    fi
    if (( unresolved )) || ! confirm_stopped; then
      status=1
      mark_unresolved
      timeout -k 5s 10s sudo -n docker logs "$C" >"$OUT/container.partial.stdout.log" \
        2>"$OUT/container.partial.stderr.log"
      # Do NOT copy changing files or label any inspection/evidence final.
    else
    cp "$OUT/container.state-unconfirmed.inspect.json" "$OUT/container.final.inspect.json"
    timeout -k 5s 10s sudo -n docker logs "$C" >"$OUT/container.stdout.log" 2>"$OUT/container.stderr.log"
    # Extract as the ordinary host user so evidence is readable without sudo.
    if ! timeout -k 5s 20s sudo -n docker cp "$C":/tmp/t59/evidence - 2>"$OUT/copy-evidence.stderr.log" \
      | tar --no-same-owner -xf - -C "$OUT"; then status=1; fi
    mkdir -p "$OUT/source-Log"
    if ! timeout -k 5s 20s sudo -n docker cp "$C":/fast_livo_ws/src/fast_livo/Log - 2>"$OUT/copy-Log.stderr.log" \
      | tar --no-same-owner -xf - -C "$OUT/source-Log"; then status=1; fi
    fi
  fi
  printf '%s\n' "$status" >"$OUT/host-runner.exit-code"
  printf 'Container retained: %s\nEvidence retained: %s\n' "$C" "$OUT"
  exit "$status"
}
interrupt() {
  trap '' INT TERM
  if (( started )); then
    stop_owned
  fi
  exit 130
}
trap collect EXIT
trap interrupt INT TERM
sudo -n docker image inspect "$IMAGE" >"$OUT/image.inspect.json"
IMAGE_ID=$(python3 - "$OUT/image.inspect.json" <<'PY'
import json, sys
with open(sys.argv[1]) as source:
    docs = json.load(source)
assert len(docs) == 1 and docs[0]["Id"].startswith("sha256:")
print(docs[0]["Id"])
PY
)
python3 - "$HERE" "$IMAGE_ID" "$MAPPER_CONFIG" "$CAMERA_CONFIG" "$SOURCE_COMMIT" "$BAG" >"$OUT/inputs.json" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
files = ["run_replay.sh", "replay.py", "replay_progress.py", "verify_replay_container.py", "playback_qos.yaml",
         "config/" + sys.argv[3], "config/" + sys.argv[4]]
print(json.dumps({"image_id": sys.argv[2], "source_commit": sys.argv[5],
                  "source_commit_status": "expected provenance; not independently rebuilt here",
                  "bag": sys.argv[6],
                  "sha256": {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}}, indent=2))
PY
COMMAND=$(python3 -B - "$HERE" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from verify_replay_container import COMMAND
print(COMMAND)
PY
)
sudo -n docker create --name "$C" \
  --network none --restart no --user 10001:10001 --workdir /fast_livo_ws \
  --memory 8g --memory-swap 8g --cpus 2 --pids-limit 512 \
  --cap-drop ALL --security-opt no-new-privileges:true --ipc private \
  --env ROS_DOMAIN_ID=173 --env ROS_LOCALHOST_ONLY=1 --env ROS2CLI_NO_DAEMON=1 \
  --env HOME=/tmp/t59 --env ROS_HOME=/tmp/t59/ros --env ROS_LOG_DIR=/tmp/t59/ros-log \
  --env OMP_NUM_THREADS=2 --env OPENBLAS_NUM_THREADS=1 --env PYTHONDONTWRITEBYTECODE=1 \
  --env "T59_IMAGE_ID=$IMAGE_ID" --entrypoint /bin/bash \
  --env "T35_PAUSED_DIAGNOSTIC=$DIAGNOSTIC" \
  --env "ASAN_OPTIONS=$ASAN_OPTIONS_VALUE" \
  --env "LD_PRELOAD=$LD_PRELOAD_VALUE" \
  --env "T35_REPLAY_RATE=$RATE" \
  --env "T35_MAPPER_CONFIG=$MAPPER_CONFIG" \
  --env "T35_CAMERA_CONFIG=$CAMERA_CONFIG" \
  "$IMAGE" -c "$COMMAND" >"$OUT/container.id"
created=1

# Daemon extraction creates writable directory ownership without runtime root.
python3 - "$HERE" "$MAPPER_CONFIG" "$CAMERA_CONFIG" <<'PY' | sudo -n docker cp -a - "$C":/
import pathlib, sys, tarfile
root = pathlib.Path(sys.argv[1])
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
    for path in ["tmp/t59", "tmp/t59/evidence", "tmp/t59/ros", "tmp/t59/ros-log",
                 "fast_livo_ws/src/fast_livo/Log", "fast_livo_ws/src/fast_livo/Log/result",
                 "fast_livo_ws/src/fast_livo/Log/pcd", "fast_livo_ws/src/fast_livo/Log/image",
                 "fast_livo_ws/src/fast_livo/Log/ref_cur_combine"]:
        info = tarfile.TarInfo(path)
        info.type, info.uid, info.gid, info.mode = tarfile.DIRTYPE, 10001, 10001, 0o750
        archive.addfile(info)
    for name in ["replay.py", "replay_progress.py", "playback_qos.yaml",
                 "config/" + sys.argv[2], "config/" + sys.argv[3]]:
        source = root / name
        if not source.is_file() or source.is_symlink():
            raise ValueError("only regular staged files accepted: " + name)
        info = archive.gettarinfo(str(source), arcname="tmp/t59/" + source.name)
        info.uid, info.gid, info.uname, info.gname, info.mode = 10001, 10001, "", "", 0o640
        with source.open("rb") as content:
            archive.addfile(info, content)
PY
# Preserve bag bytes/headers while making even mode-0600 source files readable
# by the runtime UID. GNU tar streams directly to Docker; no second host copy.
tar --numeric-owner --owner=10001 --group=10001 --mode=u+rwX \
  --transform='s,^\.,bag,' -C "$BAG" -cf - . \
  | sudo -n docker cp -a - "$C":/tmp/t59/
sudo -n docker inspect "$C" >"$OUT/container.prestart.inspect.json"
python3 -B "$HERE/verify_replay_container.py" "$OUT/container.prestart.inspect.json" "$IMAGE_ID" "$IMAGE"
CURRENT_ID=$(sudo -n docker image inspect "$IMAGE" --format '{{.Id}}')
[[ "$CURRENT_ID" == "$IMAGE_ID" ]] || { echo 'REFUSED: image tag changed during staging.' >&2; exit 1; }
check_conflicts
started=1
sudo -n docker start "$C" >"$OUT/start.log"
timeout -k 5s 650s sudo -n docker logs --follow "$C" 9>&- 2>"$OUT/progress-follow.stderr.log" &
log_pid=$!
if ! timeout -k 30s 660s sudo -n docker wait "$C" >"$OUT/container.wait.log" 2>"$OUT/wait.stderr.log"; then
  echo 'Wait failed/timed out; signal only our supervisor; no retry.' >&2
  interrupt
fi
timeout -k 5s 10s sudo -n docker inspect "$C" >"$OUT/container.exit.inspect.json"
python3 - "$OUT/container.exit.inspect.json" <<'PY'
import json, sys
with open(sys.argv[1]) as source:
    state = json.load(source)[0]["State"]
if state["Running"] or state["OOMKilled"] or state["ExitCode"] != 0 or state.get("Error"):
    sys.exit("Replay failed: " + json.dumps(state))
print("Supervisor exited 0; inspect result.json mode and verdict. A paused diagnostic is not replay acceptance.")
PY
