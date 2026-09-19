#!/bin/bash
set -e

# Derive the repo root from this script's own location, so a fresh clone works
# anywhere. Both variables below are targets of "rm -rf" further down, so they
# must never fall back to a guess.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPS_WS="$REPO/deps_ws"
ROBOT_WS="$REPO/ros2_robot_ws"

# 1. Force build deps if actual setup file is missing
if [ ! -f "$DEPS_WS/install/setup.bash" ]; then
    echo "Dependencies not found. Building deps_ws..."
    cd "$DEPS_WS"
    # It's safer to clear it first to ensure a clean state
    rm -rf build install log
    colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release
fi

# 2. Source the dependency workspace so this build can find MTC
source "$DEPS_WS/install/setup.bash"

# 3. Build the main workspace
cd "$ROBOT_WS"
echo "Cleaning robot workspace..."
rm -rf ./log ./build ./install

echo "Building rm_ros_interfaces..."
colcon build --symlink-install --packages-select rm_ros_interfaces

# 4. Source the newly built workspace so we can find the new messages
echo "Sourcing install/setup.bash..."
source ./install/setup.bash

echo "Building all packages..."
colcon build --symlink-install

echo "Done!"
