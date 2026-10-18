#!/usr/bin/env bash
# Incremental, offline experimental rebuild inside a copy of the accepted image.
set -eo pipefail
export CMAKE_BUILD_PARALLEL_LEVEL=1 MAKEFLAGS=-j1
WS=/fast_livo_ws
python3 /opt/recipe/patch_blind_sqr.py "$WS/src/fast_livo/src" /opt/recipe/blind-sqr
cp /opt/recipe/blind-sqr/src/LIVMapper.cpp "$WS/src/fast_livo/src/LIVMapper.cpp"
cd "$WS/src/fast_livo"
sha256sum -c /opt/recipe/blind-sqr/blind-sqr.sha256
source /opt/ros/humble/setup.bash
source "$WS/install/setup.bash"
cd "$WS"
colcon build --packages-select fast_livo --executor sequential --cmake-args \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DCMAKE_CXX_STANDARD=17 -DCMAKE_CXX_STANDARD_REQUIRED=ON \
    -Dvikit_common_DIR=/usr/local/lib/cmake/vikit_common
binary="$WS/install/fast_livo/lib/fast_livo/fastlivo_mapping"
# strings into a regular file avoids SIGPIPE under pipefail with grep -q.
strings "$binary" > /opt/recipe/blind-sqr/binary-strings.txt
grep -F '[T35_BLIND_SQR]' /opt/recipe/blind-sqr/binary-strings.txt
sha256sum "$binary" > /opt/recipe/blind-sqr/binary.sha256
