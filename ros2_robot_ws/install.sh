#!/bin/bash

set -e

echo "Cleaning workspace..."
rm -rf ./logs ./build ./install

echo "Building rm_ros_interfaces..."
colcon build --packages-select rm_ros_interfaces

echo "Sourcing install/setup.bash..."
source ./install/setup.bash

echo "Building all packages..."
colcon build

echo "Done!"
