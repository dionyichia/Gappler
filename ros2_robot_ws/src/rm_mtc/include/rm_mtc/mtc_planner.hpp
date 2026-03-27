#include <thread>
#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose.hpp>
#include <moveit/task_constructor/task.h>
#include <moveit/task_constructor/stages.h>
#include <moveit/task_constructor/solvers.h>

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

private:
  rclcpp::Node::SharedPtr node_;
  rclcpp::Node::SharedPtr mtc_node_;
  std::shared_ptr<rclcpp::executors::SingleThreadedExecutor> mtc_executor_;
  std::thread mtc_spin_thread_;

  const std::string ARM_GROUP = "rm_group";

  // Home pose joint values (radians)
  const std::map<std::string, double> HOME_JOINTS = {
      {"joint1", -0.0175},
      {"joint2", 0.0873},
      {"joint3", 0.9774},
      {"joint4", -3.0718},
      {"joint5", -0.4712},
      {"joint6", -3.2289},
  };
};
