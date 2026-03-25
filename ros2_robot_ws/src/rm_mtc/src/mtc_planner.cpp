#include "rm_mtc/mtc_planner.hpp"

// Stores pointer to state machine node from which it originated
MtcPlanner::MtcPlanner(const rclcpp::Node::SharedPtr& node)
: node_(node)
{}

bool MtcPlanner::executeGrasp(const geometry_msgs::msg::Pose& target_pose)
{
  Task task;
  task.stages()->setName("grasp_task");
  task.loadRobotModel(node_);

  auto arm_planner     = std::make_shared<solvers::JointInterpolationPlanner>();
  auto gripper_planner = std::make_shared<solvers::JointInterpolationPlanner>();

  // ---- Stage 0: Current state ----
  {
    auto stage = std::make_unique<stages::CurrentState>("current state");
    task.add(std::move(stage));
  }

  // ---- Stage 1: Open gripper ----
  {
    auto stage = std::make_unique<stages::MoveTo>("open gripper", gripper_planner);
    stage->setGroup(GRIPPER_GROUP);
    stage->setGoal("open");
    task.add(std::move(stage));
  }

  // ---- Stage 2: Move to grasp pose ----
  {
    auto stage = std::make_unique<stages::MoveTo>("move to grasp pose", arm_planner);
    stage->setGroup(ARM_GROUP);
    geometry_msgs::msg::PoseStamped ps;
    ps.header.frame_id = "base_link";
    ps.pose = target_pose;
    stage->setGoal(ps);
    task.add(std::move(stage));
  }

  // ---- Stage 3: Close gripper ----
  {
    auto stage = std::make_unique<stages::MoveTo>("close gripper", gripper_planner);
    stage->setGroup(GRIPPER_GROUP);
    stage->setGoal("close");
    task.add(std::move(stage));
  }

  // ---- Stage 4: Retreat to home ----
  {
    auto stage = std::make_unique<stages::MoveTo>("retreat to home", arm_planner);
    stage->setGroup(ARM_GROUP);
    stage->setGoal(HOME_JOINTS);
    task.add(std::move(stage));
  }

  // ---- Plan and execute ----
  try
  {
    task.enableIntrospection(true);
    task.init();
    if (!task.plan(5))
    {
      RCLCPP_ERROR(node_->get_logger(), "[MtcPlanner] Planning failed");
      return false;
    }
    RCLCPP_INFO(node_->get_logger(), "[MtcPlanner] Planning succeeded, executing...");
    task.execute(*task.solutions().front());
    return true;
  }
  catch (const InitStageException& e)
  {
    RCLCPP_ERROR_STREAM(node_->get_logger(), "[MtcPlanner] Stage init failed: " << e);
    return false;
  }
}