#!/usr/bin/env bash
# Canonical install/fetch/compile path, used by the bounded container and Dockerfile.
set -eo pipefail
export DEBIAN_FRONTEND=noninteractive WS=/fast_livo_ws
export CMAKE_BUILD_PARALLEL_LEVEL=1 MAKEFLAGS=-j1
# Sanitizer/debug rebuilds only; empty by default for the reviewed build.
export CXXFLAGS="${CXXFLAGS:-} ${T35_CXXFLAGS_EXTRA:-}"
export LDFLAGS="${LDFLAGS:-} ${T35_LDFLAGS_EXTRA:-}"

apt-get update
# Sanitizer runtime only when sanitizer flags are requested; the reviewed
# default build installs no additional packages. The runtime must match the
# compiling toolchain: ask g++ which file it would use, then install the
# package owning it; fall back to the newest libasan only if that fails.
if [ -n "${T35_CXXFLAGS_EXTRA:-}" ]; then
  ASAN_FILE=$(g++ -print-file-name=libasan.so)
  ASAN_PKG=$(dpkg -S "$ASAN_FILE" 2>/dev/null | cut -d: -f1 || true)
  if [ -z "$ASAN_PKG" ]; then
    ASAN_PKG=$(apt-cache search --names-only '^libasan[0-9]+$' | awk '{print $1}' | sort -V | tail -1)
  fi
  test -n "$ASAN_PKG"
  apt-get install -y --no-install-recommends "$ASAN_PKG"
fi
apt-get install -y --no-install-recommends \
    build-essential ca-certificates cmake git pkg-config \
    libapr1-dev libboost-thread-dev libeigen3-dev libfmt-dev libopencv-dev libpcl-dev \
    python3-colcon-common-extensions \
    ros-humble-ament-cmake ros-humble-ament-cmake-auto \
    ros-humble-cv-bridge ros-humble-demo-nodes-cpp \
    ros-humble-image-transport ros-humble-compressed-image-transport \
    ros-humble-geometry-msgs ros-humble-nav-msgs ros-humble-sensor-msgs \
    ros-humble-std-msgs ros-humble-visualization-msgs \
    ros-humble-pcl-conversions ros-humble-pcl-ros \
    ros-humble-rcl-interfaces ros-humble-rclcpp ros-humble-rclcpp-components \
    ros-humble-rclpy ros-humble-rcutils \
    ros-humble-ros2bag ros-humble-rosbag2 ros-humble-rosbag2-storage-default-plugins \
    ros-humble-rosidl-default-generators ros-humble-rosidl-default-runtime \
    ros-humble-rviz2 ros-humble-sophus \
    ros-humble-tf2 ros-humble-tf2-geometry-msgs ros-humble-tf2-ros

mkdir -p /opt/recipe
: > /opt/recipe/source-pins.txt
fetch_pin() {
    local url="$1" dest="$2" commit="$3"
    mkdir -p "$dest"
    cd "$dest"
    git init
    git remote add origin "$url"
    git fetch --depth 1 origin "$commit"
    git checkout --detach FETCH_HEAD
    test "$(git rev-parse HEAD)" = "$commit"
    printf '%s %s\n' "$url" "$commit" | tee -a /opt/recipe/source-pins.txt
}
fetch_pin https://github.com/Livox-SDK/Livox-SDK2.git /opt/Livox-SDK2 f5d9375f84efe2b15bc0a052d3e18482ed13adf4
fetch_pin https://github.com/Livox-SDK/livox_ros_driver2.git "$WS/src/livox_ros_driver2" 13eb05e4e6dd7a765b934d0c5fd6236676a57b49
fetch_pin https://github.com/U-AMC/rpg_vikit_rational_polynomial.git "$WS/src/rpg_vikit" 6f213c7fe6be1aff1fc79c7bd6103e3e9bc4a02d
fetch_pin https://github.com/U-AMC/FAST-LIVO2-ROS2.git "$WS/src/fast_livo" a09599a288c56b832114d7ad9e898248a4111d9e
python3 /opt/recipe/patch_cmake.py "$WS/src"
# T3.5a sampling guard: fail-closed patch for the pinned forward VIO sampler
# (ASan image overread at vio.cpp:1679). Refuses source drift instead of
# silently building unpatched code.
python3 /opt/recipe/patch_vio.py "$WS/src/fast_livo/src/vio.cpp" /tmp/vio-candidate
cp /tmp/vio-candidate/src/vio.cpp "$WS/src/fast_livo/src/vio.cpp"
cp /tmp/vio-candidate/include/patch_sampling.h "$WS/src/fast_livo/include/patch_sampling.h"
rm -rf /tmp/vio-candidate

cmake -S /opt/Livox-SDK2 -B /opt/sdk-build \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DCMAKE_CXX_STANDARD=17
cmake --build /opt/sdk-build --parallel 1
cmake --install /opt/sdk-build
ldconfig

source /opt/ros/humble/setup.bash
cmake -S "$WS/src/rpg_vikit/vikit_common" -B /opt/vikit-build \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DBUILD_TESTING=OFF -DCMAKE_CXX_STANDARD=17
cmake --build /opt/vikit-build --parallel 1
cmake --install /opt/vikit-build
mkdir -p /usr/local/lib/cmake/vikit_common
printf '%s\n' \
    'set(vikit_common_SOURCE_DIR "/usr/local")' \
    'set(vikit_common_DIR "/usr/local/lib/cmake/vikit_common")' \
    'set(vikit_common_INCLUDE_DIR "/usr/local/include")' \
    'set(vikit_common_INCLUDE_DIRS "/usr/local/include")' \
    'set(vikit_common_LIBRARIES "/usr/local/lib/libvikit_common.so")' \
    'set(vikit_common_LIBRARY "/usr/local/lib/libvikit_common.so")' \
    'set(vikit_common_LIBRARY_DIR "/usr/local/lib")' \
    'set(vikit_common_LIBRARY_DIRS "/usr/local/lib")' \
    > /usr/local/lib/cmake/vikit_common/vikit_commonConfig.cmake
ldconfig
touch "$WS/src/rpg_vikit/vikit_common/COLCON_IGNORE" "$WS/src/rpg_vikit/vikit_py/COLCON_IGNORE"
cp "$WS/src/livox_ros_driver2/package_ROS2.xml" "$WS/src/livox_ros_driver2/package.xml"
cp -r "$WS/src/livox_ros_driver2/launch_ROS2" "$WS/src/livox_ros_driver2/launch"
cd "$WS"
# shellcheck disable=SC2086: intentional word splitting of reviewed extra args
colcon build --executor sequential --cmake-args \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DCMAKE_CXX_STANDARD=17 -DCMAKE_CXX_STANDARD_REQUIRED=ON \
    -Dvikit_common_DIR=/usr/local/lib/cmake/vikit_common \
    -DROS_EDITION=ROS2 -DDISTRO_ROS=humble $T35_EXTRA_CMAKE_ARGS
useradd --create-home --uid 10001 user
if [ -n "${T35_CXXFLAGS_EXTRA:-}" ]; then
  # Fail closed: an uninstrumented binary would waste a full replay run.
  ldd "$WS/install/fast_livo/lib/fast_livo/fastlivo_mapping" | grep -q libasan
fi
printf '\nVerified source pins (before local CMake integration edits):\n'
cat /opt/recipe/source-pins.txt
