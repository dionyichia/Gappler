# MoveIt 2.5.10's moveit_core links its exported targets to tl::expected and Boost::random but
# never finds them, and ROS's tl_expected package names its target tl_expected::tl_expected.
# So any package that uses moveit_core (MTC, grasp_state_machine) fails at configure time.
# build.sh runs this file after every project() call (CMAKE_PROJECT_INCLUDE). It only defines
# what is missing, so it does nothing once MoveIt is fixed: delete it then (T1.56, 2026-10-28).
find_package(tl_expected QUIET)
if(TARGET tl_expected::tl_expected AND NOT TARGET tl::expected)
  add_library(tl::expected INTERFACE IMPORTED)
  target_link_libraries(tl::expected INTERFACE tl_expected::tl_expected)
endif()
find_package(Boost QUIET COMPONENTS random)
