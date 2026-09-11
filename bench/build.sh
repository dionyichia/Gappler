#!/usr/bin/env bash
# Tier 2 -- does it build? Compiles into THIS checkout's build/ install/ log/
# and nowhere else. Never launches a node, never touches hardware, no sudo.
#
#   ./bench/build.sh          arm workspace: ros2_robot_ws/src + deps_ws/src (24 packages)
#   ./bench/build.sh nav      Navigation_Module/src, into build_nav/ install_nav/
#
# Run from a fresh shell: only /opt/ros/humble may be sourced -- a stale
# overlay on AMENT_PREFIX_PATH poisons the build (startup guide section 2).
# Exit: 0 all packages built, 1 a package failed, 3 SKIPPED (no ROS here --
# never reported as a pass).
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${1:-arm}"

case "$target" in
  arm) paths=(ros2_robot_ws/src deps_ws/src); bdir=build;     idir=install ;;
  nav) paths=(Navigation_Module/src);         bdir=build_nav; idir=install_nav ;;
  *)   echo "usage: $0 [arm|nav]"; exit 2 ;;
esac

if [ ! -f /opt/ros/humble/setup.bash ]; then
  echo "SKIP: no ROS 2 Humble on this machine -- build can only be judged on the lab box"; exit 3
fi
if [ -n "${AMENT_PREFIX_PATH:-}" ] && [ "$AMENT_PREFIX_PATH" != "/opt/ros/humble" ]; then
  echo "FAIL: an overlay is already sourced (AMENT_PREFIX_PATH=$AMENT_PREFIX_PATH)."
  echo "      Open a fresh shell; this script sources /opt/ros/humble itself."; exit 1
fi
source /opt/ros/humble/setup.bash
cd "$REPO"
mkdir -p log
out="log/bench_build_${target}_$(date +%F_%H%M).txt"

echo "Tier 2 build [$target]: ${paths[*]} -> $bdir/ $idir/   (log: $out)"
start=$(date +%s)
# MAKEFLAGS caps compile jobs so a shared machine stays usable.
MAKEFLAGS="-j${BENCH_JOBS:-8}" colcon build \
  --base-paths "${paths[@]}" --build-base "$bdir" --install-base "$idir" \
  --cmake-args -DCMAKE_BUILD_TYPE=Release \
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
