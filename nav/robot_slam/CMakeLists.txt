cmake_minimum_required(VERSION 3.8)
project(robot_slam)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}/
)
# The node scripts moved to one package each (nav/object_approach, nav/goto_glasses, ...) 2026-09-22.

ament_package()
