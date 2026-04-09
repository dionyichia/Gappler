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
  const std::map<std::string, double> HOME_JOINTS = {
      {"joint1", 0.0},    // 0 degrees
      {"joint2", 0.0},    // 0 degrees
      {"joint3", 0.7854}, // 45 degrees
      {"joint4", 0.0},    // 0 degrees
      {"joint5", 1.5708}, // 90 degrees
      {"joint6", 1.5708}, // 90 degrees
  };

  // Return pose joint values (radians)
  const std::map<std::string, double> RETURN_JOINTS = {
      {"joint1", 0.0},     // 0 degrees
      {"joint2", -0.2443}, // -14 degrees
      {"joint3", 2.3562},  // 135 degrees
      {"joint4", 0.0},     // 0 degrees
      {"joint5", -0.5585}, // -32 degrees
      {"joint6", 1.5708},  // 90 degrees
  };
};
