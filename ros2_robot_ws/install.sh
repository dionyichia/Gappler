#!/bin/bash

set -e

if [ ! -d "$HOME/deps_ws/install" ]; then
    echo "Building dependencies in ~/deps_ws..."
    (cd "$HOME/deps_ws" && colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release)
fi

# Source the dependency workspace so this build can find MTC
source "$HOME/deps_ws/install/setup.bash"

echo "Cleaning workspace..."
rm -rf ./logs ./build ./install

echo "Building rm_ros_interfaces..."
colcon build --packages-select rm_ros_interfaces

echo "Sourcing install/setup.bash..."
source ./install/setup.bash

echo "Building all packages..."
colcon build --symlink-install



echo "Done!"
