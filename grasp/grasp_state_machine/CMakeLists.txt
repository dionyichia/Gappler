cmake_minimum_required(VERSION 3.8)
project(grasp_state_machine)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(moveit_task_constructor_core REQUIRED)
find_package(moveit_ros_planning_interface REQUIRED)
find_package(geometry_msgs REQUIRED)
# uncomment the following section in order to fill in
# further dependencies manually.
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(rm_ros_interfaces REQUIRED)   # the gripper messages (RealMan's)
find_package(grasp_interfaces REQUIRED)    # GraspCandidate(Array), ours
find_package(std_msgs REQUIRED)
find_package(moveit_msgs REQUIRED)
find_package(shape_msgs REQUIRED)

add_executable(grasp_state_machine
  src/grasp_state_machine.cpp
  src/mtc_planner.cpp)
target_include_directories(grasp_state_machine PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(grasp_state_machine PUBLIC c_std_99 cxx_std_17)  # Require C99 and C++17
ament_target_dependencies(grasp_state_machine
  rclcpp
  moveit_task_constructor_core
  moveit_ros_planning_interface
  geometry_msgs
  tf2_ros
  tf2_geometry_msgs
  rm_ros_interfaces
  grasp_interfaces
  std_msgs
  moveit_msgs
  shape_msgs  
)

install(TARGETS grasp_state_machine
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
