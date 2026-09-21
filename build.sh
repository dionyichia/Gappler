#!/usr/bin/env bash
# Builds our ROS code into THIS checkout's build/ install/ log/ and nowhere else.
# env.sh sources the result. The bench runs it as L3 (was bench/build.sh until 2026-09-21).
# Never launches a node, never touches hardware, no sudo.
#
#   ./build.sh          arm/ + grasp/, vendor included (24 packages)
#   ./build.sh nav      nav/, vendor included, into build_nav/ install_nav/
#
# --symlink-install: install/ links back to the repo instead of copying, so a Python
# or launch-file edit takes effect without a rebuild. Switching an existing install/
# to it needs one clean rebuild (rm -rf build install).
#
# nav does the Livox prep livox_ros_driver2/build.sh:50-67 would do: if the
# (gitignored) livox package.xml is missing, copy in the ROS 2 template
# (nav/vendor/livox_ros_driver2/package_ROS2.xml; delete the copy to undo), and pass
# -DROS_EDITION=ROS2 -DHUMBLE_ROS=humble. It does not install Livox-SDK2 (that
# needs sudo); it says so up front if the library isn't there.
#
# Run from a fresh shell: only /opt/ros/humble may be sourced -- a stale
# overlay on AMENT_PREFIX_PATH poisons the build (startup guide section 2).
# Exit: 0 all packages built, 1 a package failed, 3 SKIPPED (no ROS here --
# never reported as a pass).
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # this file sits at the repo root
target="${1:-arm}"

case "$target" in
  arm) paths=(arm grasp); bdir=build;     idir=install;     extra=() ;;
  nav) paths=(nav);       bdir=build_nav; idir=install_nav
       extra=(-DROS_EDITION=ROS2 -DHUMBLE_ROS=humble) ;;
  *)   echo "usage: $0 [arm|nav]"; exit 2 ;;
esac

if [ ! -f /opt/ros/humble/setup.bash ]; then
  echo "SKIP: no ROS 2 Humble on this machine -- build can only be judged on the lab box"; exit 3
fi
if [ -n "${AMENT_PREFIX_PATH:-}" ] && [ "$AMENT_PREFIX_PATH" != "/opt/ros/humble" ]; then
  echo "FAIL: an overlay is already sourced (AMENT_PREFIX_PATH=$AMENT_PREFIX_PATH)."
  echo "      Open a fresh shell; this script sources /opt/ros/humble itself."; exit 1
fi
set +u; source /opt/ros/humble/setup.bash; set -u   # ROS's setup reads unset vars
cd "$REPO"
mkdir -p log
out="log/bench_build_${target}_$(date +%F_%H%M).txt"

if [ "$target" = nav ]; then
  livox=nav/vendor/livox_ros_driver2
  if [ ! -f "$livox/package.xml" ]; then
    cp "$livox/package_ROS2.xml" "$livox/package.xml"
    echo "prep: $livox/package.xml was missing (gitignored, ORIENTATION 8.15);"
    echo "      copied $livox/package_ROS2.xml there. rm it to undo."
  else
    echo "prep: $livox/package.xml exists; left as is"
  fi
  # livox CMakeLists.txt:249 -- find_library(liblivox_lidar_sdk_shared.so ... REQUIRED)
  if [ -f /usr/local/lib/liblivox_lidar_sdk_shared.so ] || ldconfig -p 2>/dev/null | grep -q liblivox_lidar_sdk_shared; then
    echo "prep: Livox-SDK2 library found"
  else
    echo "note: Livox-SDK2 (liblivox_lidar_sdk_shared.so) is not installed; livox_ros_driver2 will"
    echo "      fail at find_library. Installing it needs sudo -- not done by the bench."
  fi
fi

echo "Build [$target]: ${paths[*]} -> $bdir/ $idir/   (log: $out)"
start=$(date +%s)
# MAKEFLAGS caps compile jobs so a shared machine stays usable.
MAKEFLAGS="-j${BENCH_JOBS:-8}" colcon build \
  --base-paths "${paths[@]}" --build-base "$bdir" --install-base "$idir" --symlink-install \
  --cmake-args -DCMAKE_BUILD_TYPE=Release ${extra[@]+"${extra[@]}"} \
  --event-handlers console_direct- console_cohesion+ 2>&1 | tee "$out" >/dev/null
rc=${PIPESTATUS[0]}
secs=$(( $(date +%s) - start ))

echo
grep -E "^Summary:|packages? (failed|aborted|had stderr output|not processed)" "$out" || true
echo "Elapsed: $((secs/60)) min $((secs%60)) s   colcon exit: $rc"
if [ "$rc" -eq 0 ]; then
  echo "PASS: every package built. Overlay: $REPO/$idir/setup.bash"
else
  echo "FAIL: see the failed-package list above and $out"
fi
exit $(( rc == 0 ? 0 : 1 ))
