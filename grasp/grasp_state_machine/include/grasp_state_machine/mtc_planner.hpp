#include <thread>
#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <moveit/task_constructor/task.h>
#include <moveit/task_constructor/stages.h>
#include <moveit/task_constructor/solvers.h>
#include <moveit/move_group_interface/move_group_interface.h>

using namespace moveit::task_constructor;

class MtcPlanner
{
public:
  MtcPlanner(const rclcpp::Node::SharedPtr &node);

  ~MtcPlanner()
  {
    mtc_executor_->cancel();
    if (mtc_spin_thread_.joinable())
      mtc_spin_thread_.join();
  }
  // Moves arm to the given target_pose (in base_link frame).
  // Returns true on success, false on planning or execution failure.
  bool moveToPose(const geometry_msgs::msg::Pose &target_pose);

  // Moves arm back to the defined home joint configuration.
  // Returns true on success, false on planning or execution failure.
  bool moveToHome();
  bool moveToReturn();

  geometry_msgs::msg::PoseStamped getCurrentPose();

  bool moveCartesianStep(const geometry_msgs::msg::Pose &goal_pose_base);

private:
  rclcpp::Node::SharedPtr node_;
  rclcpp::Node::SharedPtr mtc_node_;
  std::shared_ptr<rclcpp::executors::SingleThreadedExecutor> mtc_executor_;
  std::shared_ptr<moveit::planning_interface::MoveGroupInterface> move_group_;
  std::thread mtc_spin_thread_;

  const std::string ARM_GROUP = "rm_group";

  // Home pose joint values (radians)
  // Validated on the real arm 2026-09-23 (T1.7): commanded one joint at a time through
  // /rm_driver/movej_cmd, the arm reached every joint within 0.0004 rad (0.02 deg) of
  // these values, so they stand unchanged. The tool ends up in front of the arm's base,
  // which was checked and accepted at the robot. Evidence:
  // docs/dion_docs/T1.7_FIRST_COMMANDED_MOTION.md
  const std::map<std::string, double> HOME_JOINTS = {
      {"joint1", 0.0},    // 0 degrees
      {"joint2", 0.0},    // 0 degrees
      {"joint3", 0.7854}, // 45 degrees
      {"joint4", 0.0},    // 0 degrees
      {"joint5", 1.5708}, // 90 degrees
      {"joint6", 1.5708}, // 90 degrees
  };

  // Return pose: the home pose for now (Dion, 2026-10-05). HOME is the only pose
  // validated on the real arm (T1.7), and a real hand-to-user pose is future work.
  // The old row (joint3 2.3000, never run on the real arm) is in git history.
  const std::map<std::string, double> RETURN_JOINTS = HOME_JOINTS;
};
