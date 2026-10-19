#!/usr/bin/env bash
# Incremental, offline experimental rebuild inside a copy of the accepted image.
set -eo pipefail
export CMAKE_BUILD_PARALLEL_LEVEL=1 MAKEFLAGS=-j1
WS=/fast_livo_ws
BASELINE="${1:-pinned}"
test "$#" -le 1 || { echo 'Expected at most one reviewed baseline' >&2; exit 1; }
case "$BASELINE" in pinned|visibility-voxel) ;; *) echo 'Unknown blind_sqr baseline' >&2; exit 1;; esac
verify_visual_sources() {
  (cd "$WS/src/fast_livo"
   printf '%s\n' \
     '60f3c99b526af61b20a9aa75dd0397c77dd74bdad37e87ebe1b1380e16ee816c  src/vio.cpp' \
     '9e3e66edd4f7323a5bd698ce3abdf229ba81486b96a3af66e893362dcb4e7f00  include/visual_geometry.h' \
     | sha256sum -c -)
}
if [ "$BASELINE" = visibility-voxel ]; then
  verify_visual_sources
fi
python3 /opt/recipe/patch_blind_sqr.py "$WS/src/fast_livo/src" /opt/recipe/blind-sqr --baseline "$BASELINE"
cp /opt/recipe/blind-sqr/src/LIVMapper.cpp "$WS/src/fast_livo/src/LIVMapper.cpp"
cd "$WS/src/fast_livo"
sha256sum -c /opt/recipe/blind-sqr/blind-sqr.sha256
if [ "$BASELINE" = visibility-voxel ]; then
  sha256sum src/vio.cpp include/visual_geometry.h > /opt/recipe/blind-sqr/inherited-visual.sha256
fi
source /opt/ros/humble/setup.bash
source "$WS/install/setup.bash"
cd "$WS"
colcon build --packages-select fast_livo --executor sequential --cmake-args \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DCMAKE_CXX_STANDARD=17 -DCMAKE_CXX_STANDARD_REQUIRED=ON \
    -Dvikit_common_DIR=/usr/local/lib/cmake/vikit_common
if [ "$BASELINE" = visibility-voxel ]; then
  verify_visual_sources
  (cd "$WS/src/fast_livo"; sha256sum -c /opt/recipe/blind-sqr/blind-sqr.sha256)
fi
binary="$WS/install/fast_livo/lib/fast_livo/fastlivo_mapping"
# strings into a regular file avoids SIGPIPE under pipefail with grep -q.
strings "$binary" > /opt/recipe/blind-sqr/binary-strings.txt
grep -F '[T35_BLIND_SQR]' /opt/recipe/blind-sqr/binary-strings.txt
if [ "$BASELINE" = visibility-voxel ]; then
  grep -F '[T35_DIAG_RETRIEVE]' /opt/recipe/blind-sqr/binary-strings.txt
  grep -F '[T35_DIAG_CLOUD]' /opt/recipe/blind-sqr/binary-strings.txt
fi
sha256sum "$binary" > /opt/recipe/blind-sqr/binary.sha256
