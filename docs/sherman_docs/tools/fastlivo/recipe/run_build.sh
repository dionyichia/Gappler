#!/usr/bin/env bash
# User-run only. Ordinary container, not a BuildKit/docker-container builder.
set -eo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
COMBINED="${T35_COMBINED_REPAIR:-0}"
case "$COMBINED" in 0|1) ;; *) echo 'T35_COMBINED_REPAIR must be 0 or 1' >&2; exit 1;; esac
DIAGNOSTIC="${T35_VIO_DIAGNOSTIC:-0}"
case "$DIAGNOSTIC" in 0|1) ;; *) echo 'T35_VIO_DIAGNOSTIC must be 0 or 1' >&2; exit 1;; esac
REPAIR="${T35_VIO_REPAIR:-none}"
case "$REPAIR" in none|visibility|visibility-voxel) ;; *) echo 'Unknown visual repair stage' >&2; exit 1;; esac
BLIND_SQR="${T35_BLIND_SQR:-0}"
case "$BLIND_SQR" in 0|1) ;; *) echo 'T35_BLIND_SQR must be 0 or 1' >&2; exit 1;; esac
if [ "$COMBINED" = 1 ] && { [ "$BLIND_SQR" != 0 ] || [ "$DIAGNOSTIC" != 0 ] || [ "$REPAIR" != none ]; }; then
  echo 'combined mode requires other selectors off' >&2; exit 1
fi
if [ "$REPAIR" != none ] && [ "$DIAGNOSTIC" != 1 ]; then
  echo 'Visual repair requires explicit T35_VIO_DIAGNOSTIC=1' >&2; exit 1
fi
if [ "$BLIND_SQR" = 1 ] && [ "$DIAGNOSTIC" = 1 ]; then
  echo 'T35_BLIND_SQR is its own mode; do not combine it with T35_VIO_DIAGNOSTIC' >&2; exit 1
fi
DIAGNOSTIC_BASE=sha256:d0dcfa8af10fa8d1b2f1cf42434ab1b763838d798139f266da7bcc65719de8b1
COMBINED_BASE=sha256:2fa9f264ab48a01942b706f1a93a29d798f09d64e2ca7e0c314cf3cc32df81a2
NETWORK=bridge
if [ "$COMBINED" = 1 ]; then
  DEFAULT_NAME=t35-fastlivo-visibility-voxel-blind-sqr-build
  EXPECTED_IMAGE=t35-fastlivo-visibility-voxel-blind-sqr:experimental
  NAME="${T35_BUILD_NAME:-$DEFAULT_NAME}"
  IMAGE="${T35_BUILD_IMAGE:-$EXPECTED_IMAGE}"
  NETWORK=none
  if [ "$IMAGE" != "$EXPECTED_IMAGE" ] || [ -n "${T35_CXXFLAGS_EXTRA:-}${T35_LDFLAGS_EXTRA:-}${T35_EXTRA_CMAKE_ARGS:-}" ]; then
    echo 'combined build must use a separate image and unchanged compiler options' >&2; exit 1
  fi
elif [ "$BLIND_SQR" = 1 ]; then
  DEFAULT_NAME=t35-fastlivo-blind-sqr-build
  EXPECTED_IMAGE=t35-fastlivo-blind-sqr:experimental
  NAME="${T35_BUILD_NAME:-$DEFAULT_NAME}"
  IMAGE="${T35_BUILD_IMAGE:-$EXPECTED_IMAGE}"
  NETWORK=none
  if [ "$IMAGE" != "$EXPECTED_IMAGE" ] || [ -n "${T35_CXXFLAGS_EXTRA:-}${T35_LDFLAGS_EXTRA:-}${T35_EXTRA_CMAKE_ARGS:-}" ]; then
    echo 'blind_sqr build must use a separate image and unchanged compiler options' >&2; exit 1
  fi
elif [ "$DIAGNOSTIC" = 1 ]; then
  case "$REPAIR" in
    none) DEFAULT_NAME=t35-fastlivo-vio-diagnostic-build; EXPECTED_IMAGE=t35-fastlivo-vio-diagnostic:experimental ;;
    visibility) DEFAULT_NAME=t35-fastlivo-visibility-build; EXPECTED_IMAGE=t35-fastlivo-visibility:experimental ;;
    visibility-voxel) DEFAULT_NAME=t35-fastlivo-visibility-voxel-build; EXPECTED_IMAGE=t35-fastlivo-visibility-voxel:experimental ;;
  esac
  NAME="${T35_BUILD_NAME:-$DEFAULT_NAME}"
  IMAGE="${T35_BUILD_IMAGE:-$EXPECTED_IMAGE}"
  NETWORK=none
  if [ "$IMAGE" != "$EXPECTED_IMAGE" ] || [ -n "${T35_CXXFLAGS_EXTRA:-}${T35_LDFLAGS_EXTRA:-}${T35_EXTRA_CMAKE_ARGS:-}" ]; then
    echo 'diagnostic build must use a separate image and unchanged compiler options' >&2; exit 1
  fi
else
  NAME="${T35_BUILD_NAME:-t59-fastlivo-build}"
  IMAGE="${T35_BUILD_IMAGE:-t59-fast-livo2:experimental}"
fi
command -v python3 >/dev/null
command -v docker >/dev/null
command -v flock >/dev/null
command -v pgrep >/dev/null
test -t 0 || { echo 'Run from an interactive terminal for sudo authentication.' >&2; exit 1; }
# Cooperative lock: other tools must use this same lock to participate.
exec 9>"$HOME/rcp-Gappler/log/software-build.lock"
flock -n 9 || { echo 'Another cooperating build holds the lab lock.' >&2; exit 1; }
check_host_idle() {
    local status=0
    pgrep -af 'Runner[.]Worker|bench/run[.]sh|(^|/|[[:space:]])colcon([[:space:]]|$)|ros2[[:space:]]+launch|rm_driver|xnode_vehicle|livox_ros_driver|realsense2_camera_node|fastlivo_mapping|docker[[:space:]]+(build|buildx[[:space:]]+build)' || status=$?
    if [ "$status" -eq 0 ]; then
        echo 'Potential competing robot/bench/build activity above; stop and coordinate. No process stopped.' >&2
        return 1
    fi
    if [ "$status" -ne 1 ]; then
        echo 'Process inspection failed; refusing build.' >&2
        return 1
    fi
}
check_host_idle
sudo -v
python3 -B test_recipe.py
python3 -B test_diagnostics.py
python3 -B test_visual_fixes.py
python3 -B test_blind_sqr.py
python3 -B test_combined.py
# Overrides for sanitizer/debug rebuilds only; defaults build the reviewed image.
BASE=ros:humble-perception-jammy
if [[ "$COMBINED" = 0 && "$DIAGNOSTIC" = 0 && "$BLIND_SQR" = 0 && "$IMAGE" != "t59-fast-livo2:experimental" && -z "${T35_CXXFLAGS_EXTRA:-}" ]]; then
  echo 'REFUSED: an overridden build image requires T35_CXXFLAGS_EXTRA (e.g. the documented AddressSanitizer flags).' >&2
  exit 1
fi
LOGDIR=$(mktemp -d "$PWD/build-logs.XXXXXX")
echo "Logs: $LOGDIR; container and logs are retained, including on failure."
sudo docker info --format '{{json .}}' > "$LOGDIR/daemon.json"
python3 - "$LOGDIR/daemon.json" <<'PY'
import json, sys
info = json.load(open(sys.argv[1]))
print('Daemon memory bytes:', info.get('MemTotal'), 'CPUs:', info.get('NCPU'))
for warning in info.get('Warnings') or []:
    print('DAEMON WARNING:', warning)
for key in ('MemoryLimit', 'SwapLimit', 'CpuCfsQuota', 'CpuCfsPeriod', 'PidsLimit'):
    alias = key.replace('Cpu', 'CPU')
    if info.get(key, info.get(alias)) is not True:
        raise SystemExit('Required cgroup capability absent/unknown: ' + key)
if info.get('MemTotal', 0) < 8589934592 or info.get('NCPU', 0) < 2:
    print('WARNING: daemon has less than 8 GiB RAM or 2 CPUs; build may fail or be slow.')
PY

# Inspect existing builder containers read-only; never create, start, or change them.
sudo docker ps -a --filter name=buildx_buildkit --format '{{.ID}}' > "$LOGDIR/existing-builders.txt"
while IFS= read -r builder; do
    test -n "$builder" || continue
    sudo docker inspect "$builder" > "$LOGDIR/builder-$builder.json"
    sudo docker inspect --format 'Existing builder {{.Name}} HostConfig={{json .HostConfig}}' "$builder"
done < "$LOGDIR/existing-builders.txt"

sudo docker ps -a --format '{{.Names}}' > "$LOGDIR/container-names.txt"
if grep -Fxq "$NAME" "$LOGDIR/container-names.txt"; then
    echo "Refusing existing container: $NAME" >&2; exit 1
fi
sudo docker image ls --format '{{.Repository}}:{{.Tag}}' > "$LOGDIR/image-tags.txt"
if grep -Fxq "$IMAGE" "$LOGDIR/image-tags.txt"; then
    echo "Refusing existing image tag: $IMAGE" >&2; exit 1
fi
check_host_idle
if [ "$COMBINED" = 1 ]; then
  sudo docker image inspect "$COMBINED_BASE" > "$LOGDIR/base-image.json"
  BASE_DIGEST="$COMBINED_BASE"
elif [ "$DIAGNOSTIC" = 1 ] || [ "$BLIND_SQR" = 1 ]; then
  # No pull, package installation or dependency rebuild in these modes.
  sudo docker image inspect "$DIAGNOSTIC_BASE" > "$LOGDIR/base-image.json"
  BASE_DIGEST="$DIAGNOSTIC_BASE"
else
sudo docker pull "$BASE" 2>&1 | tee "$LOGDIR/pull.log"
sudo docker image inspect --format '{{join .RepoDigests "\n"}}' "$BASE" | tee "$LOGDIR/base-digests.txt"
BASE_DIGEST=$(head -n 1 "$LOGDIR/base-digests.txt")
case "$BASE_DIGEST" in *@sha256:*) ;; *) echo 'Missing pulled base digest' >&2; exit 1;; esac
fi

echo 'Intended hard limits: Memory=8589934592 MemorySwap=8589934592 NanoCpus=2000000000 PidsLimit=512'
echo "Ordinary container; network $NETWORK; no privileges, mounts, devices, or Docker socket."
echo "Build overrides: NAME=$NAME IMAGE=$IMAGE CXXFLAGS_EXTRA=${T35_CXXFLAGS_EXTRA:-<none>}"
if [ "$DIAGNOSTIC" = 1 ]; then
  echo 'Diagnostic only: exact accepted image, network none, mapper-only rebuild; no acceptance claim.'
  sudo docker create --name "$NAME" --memory 8g --memory-swap 8g --cpus 2 \
      --pids-limit 512 --network none --user root --env "T35_VIO_REPAIR=$REPAIR" --entrypoint bash "$BASE_DIGEST" \
      -c 'set -eo pipefail; cp /diagnostic_inside.sh /patch_diagnostics.py /patch_visual_fixes.py /visual_geometry.h /opt/recipe/; exec bash /opt/recipe/diagnostic_inside.sh' \
      | tee "$LOGDIR/container-id.txt"
  sudo docker cp diagnostic_inside.sh "$NAME:/diagnostic_inside.sh"
  sudo docker cp patch_diagnostics.py "$NAME:/patch_diagnostics.py"
  sudo docker cp patch_visual_fixes.py "$NAME:/patch_visual_fixes.py"
  sudo docker cp visual_geometry.h "$NAME:/visual_geometry.h"
elif [ "$BLIND_SQR" = 1 ] || [ "$COMBINED" = 1 ]; then
  BLIND_ENTRY='set -eo pipefail; cp /blind_sqr_inside.sh /patch_blind_sqr.py /opt/recipe/; exec bash /opt/recipe/blind_sqr_inside.sh'
  if [ "$COMBINED" = 1 ]; then
    echo 'Combined candidate: exact visibility+voxel image plus F2, network none, mapper-only; no acceptance claim.'
    BLIND_ENTRY="$BLIND_ENTRY visibility-voxel"
  else
    echo 'F2 blind_sqr fix only: exact accepted image, network none, mapper-only rebuild; no acceptance claim.'
  fi
  sudo docker create --name "$NAME" --memory 8g --memory-swap 8g --cpus 2 \
      --pids-limit 512 --network none --user root --entrypoint bash "$BASE_DIGEST" \
      -c "$BLIND_ENTRY" \
      | tee "$LOGDIR/container-id.txt"
  sudo docker cp blind_sqr_inside.sh "$NAME:/blind_sqr_inside.sh"
  sudo docker cp patch_blind_sqr.py "$NAME:/patch_blind_sqr.py"
else
sudo docker create --name "$NAME" --memory 8g --memory-swap 8g --cpus 2 \
    --pids-limit 512 --network bridge --entrypoint bash \
    --env "T35_CXXFLAGS_EXTRA=${T35_CXXFLAGS_EXTRA:-}" \
    --env "T35_LDFLAGS_EXTRA=${T35_LDFLAGS_EXTRA:-}" \
    --env "T35_EXTRA_CMAKE_ARGS=${T35_EXTRA_CMAKE_ARGS:-}" \
    "$BASE_DIGEST" \
    -c 'set -eo pipefail; mkdir -p /opt/recipe; cp /build_inside.sh /patch_cmake.py /patch_vio.py /patch_sampling.h /opt/recipe/; exec bash /opt/recipe/build_inside.sh' \
    | tee "$LOGDIR/container-id.txt"
sudo docker cp build_inside.sh "$NAME:/build_inside.sh"
sudo docker cp patch_cmake.py "$NAME:/patch_cmake.py"
sudo docker cp patch_vio.py "$NAME:/patch_vio.py"
sudo docker cp patch_sampling.h "$NAME:/patch_sampling.h"
fi
sudo docker inspect "$NAME" > "$LOGDIR/pre-inspect.json"
sudo docker inspect --format '{{json .HostConfig}}' "$NAME" | tee "$LOGDIR/hostconfig.json"
python3 -B check_container.py pre "$LOGDIR/pre-inspect.json" "$NAME" "$NETWORK"

# Disable errexit only to collect the attached-client and tee status plus final state.
check_host_idle
set +e
sudo docker start -a "$NAME" 2>&1 | tee "$LOGDIR/build.log"
statuses=("${PIPESTATUS[@]}")
set -e
sudo docker inspect "$NAME" > "$LOGDIR/post-inspect.json"
sudo docker inspect --format '{{json .State}}' "$NAME" | tee "$LOGDIR/state.json"
python3 -B check_container.py post "$LOGDIR/post-inspect.json" "$NAME" "$NETWORK"
test "${statuses[0]}" -eq 0 && test "${statuses[1]}" -eq 0
sudo docker cp "$NAME:/opt/recipe/source-pins.txt" "$LOGDIR/source-pins.txt"
if [ "$DIAGNOSTIC" = 1 ]; then
  sudo docker cp "$NAME:/opt/recipe/vio-diagnostic" "$LOGDIR/vio-diagnostic"
  if [ "$REPAIR" != none ]; then
    sudo docker cp "$NAME:/opt/recipe/visual-fixes" "$LOGDIR/visual-fixes"
  fi
fi
if [ "$BLIND_SQR" = 1 ] || [ "$COMBINED" = 1 ]; then
  sudo docker cp "$NAME:/opt/recipe/blind-sqr" "$LOGDIR/blind-sqr"
fi
# Recheck before committing; never intentionally replace another run's image tag.
sudo docker image ls --format '{{.Repository}}:{{.Tag}}' > "$LOGDIR/final-image-tags.txt"
if grep -Fxq "$IMAGE" "$LOGDIR/final-image-tags.txt"; then
    echo "Refusing image tag that appeared during build: $IMAGE" >&2; exit 1
fi
sudo docker commit --change 'USER user' --change 'WORKDIR /fast_livo_ws' \
    --change 'ENTRYPOINT []' --change 'CMD ["bash"]' "$NAME" "$IMAGE" \
    | tee "$LOGDIR/commit.log"
echo "Experimental image created: $IMAGE. Stopped container $NAME and logs retained in $LOGDIR."
