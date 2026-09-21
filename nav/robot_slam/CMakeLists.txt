cmake_minimum_required(VERSION 3.8)
project(robot_slam)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}/
)
install(PROGRAMS
  scripts/qos_relay.py
  scripts/pose_publisher.py
  scripts/goal_reached_publisher.py
  scripts/goto_glasses.py
  scripts/aria_image_relay.py
  scripts/object_approach_node.py
  DESTINATION lib/${PROJECT_NAME})

ament_package()
