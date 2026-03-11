#!/bin/bash

set -e

if [ ! -d "$HOME/GitHub/Renaissance-Capstone-Project/deps_ws/install" ]; then
    echo "Building dependencies in deps_ws..."
    (cd "$HOME/GitHub/Renaissance-Capstone-Project/deps_ws" && colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release)
fi

# Source the dependency workspace so this build can find MTC
source "$HOME/GitHub/Renaissance-Capstone-Project/deps_ws/install/setup.bash"

echo "Cleaning workspace..."
rm -rf ./log ./build ./install

echo "Building rm_ros_interfaces..."
colcon build --symlink-install --packages-select rm_ros_interfaces

echo "Sourcing install/setup.bash..."
source ./install/setup.bash

echo "Building all packages..."
colcon build --symlink-install



echo "Done!"
