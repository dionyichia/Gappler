#!/usr/bin/env bash
# Incremental, offline experimental rebuild inside a copy of the accepted image.
set -eo pipefail
export CMAKE_BUILD_PARALLEL_LEVEL=1 MAKEFLAGS=-j1
WS=/fast_livo_ws
python3 /opt/recipe/patch_diagnostics.py "$WS/src/fast_livo/src" /opt/recipe/vio-diagnostic
cp /opt/recipe/vio-diagnostic/src/vio.cpp "$WS/src/fast_livo/src/vio.cpp"
cp /opt/recipe/vio-diagnostic/src/LIVMapper.cpp "$WS/src/fast_livo/src/LIVMapper.cpp"
cd "$WS/src/fast_livo"
sha256sum -c /opt/recipe/vio-diagnostic/vio-diagnostic.sha256
if [ "${T35_VIO_REPAIR:-none}" != none ]; then
  python3 /opt/recipe/patch_visual_fixes.py "$WS/src/fast_livo/src/vio.cpp" \
      "$T35_VIO_REPAIR" /opt/recipe/visual-fixes
  cp /opt/recipe/visual-fixes/src/vio.cpp "$WS/src/fast_livo/src/vio.cpp"
  cp /opt/recipe/visual-fixes/include/visual_geometry.h "$WS/src/fast_livo/include/visual_geometry.h"
  sha256sum -c /opt/recipe/visual-fixes/visual-fixes.sha256
  echo "Visual repair candidate: $T35_VIO_REPAIR (not replay acceptance)"
fi
source /opt/ros/humble/setup.bash
source "$WS/install/setup.bash"
cd "$WS"
colcon build --packages-select fast_livo --executor sequential --cmake-args \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DCMAKE_CXX_STANDARD=17 -DCMAKE_CXX_STANDARD_REQUIRED=ON \
    -Dvikit_common_DIR=/usr/local/lib/cmake/vikit_common
binary="$WS/install/fast_livo/lib/fast_livo/fastlivo_mapping"
# strings into a regular file avoids SIGPIPE under pipefail with grep -q.
strings "$binary" > /opt/recipe/vio-diagnostic/binary-strings.txt
grep -F '[T35_DIAG_RETRIEVE]' /opt/recipe/vio-diagnostic/binary-strings.txt
grep -F '[T35_DIAG_CLOUD]' /opt/recipe/vio-diagnostic/binary-strings.txt
sha256sum "$binary" > /opt/recipe/vio-diagnostic/binary.sha256
