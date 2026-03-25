#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose.hpp>
#include <moveit/task_constructor/task.h>
#include <moveit/task_constructor/stages.h>
#include <moveit/task_constructor/solvers.h>

using namespace moveit::task_constructor;

class MtcPlanner
{
public:
  MtcPlanner(const rclcpp::Node::SharedPtr& node);

  // Plans and executes a grasp at target_pose, then retreats to home.
  // Returns true on success, false on planning or execution failure.
  bool executeGrasp(const geometry_msgs::msg::Pose& target_pose);

private:
  rclcpp::Node::SharedPtr node_;

  const std::string ARM_GROUP    = "rm_group";
  const std::string GRIPPER_GROUP = "gripper";

  // Home pose joint values (radians)
  const std::map<std::string, double> HOME_JOINTS = {
    {"joint1", -0.0175},
    {"joint2",  0.0873},
    {"joint3",  0.9774},
    {"joint4", -3.0718},
    {"joint5", -0.4712},
    {"joint6", -3.2289},
  };
};
