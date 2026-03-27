#include "rm_mtc/mtc_planner.hpp"

// Stores pointer to state machine node from which it originated
MtcPlanner::MtcPlanner(const rclcpp::Node::SharedPtr &node)
    : node_(node)
{
  mtc_node_ = std::make_shared<rclcpp::Node>(
      "mtc_planner_node",
      rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true));
  mtc_executor_ = std::make_shared<rclcpp::executors::SingleThreadedExecutor>();
  mtc_executor_->add_node(mtc_node_);
  mtc_spin_thread_ = std::thread([this]()
                                 { mtc_executor_->spin(); });
}

// *** CHANGED: replaces executeGrasp(), handles arm motion to target pose only ***
bool MtcPlanner::moveToPose(const geometry_msgs::msg::Pose &target_pose)
{
  Task task;
  task.stages()->setName("move_to_pose");
  task.loadRobotModel(mtc_node_);

  auto arm_planner = std::make_shared<solvers::JointInterpolationPlanner>();

  // ---- Stage 0: Current state ----
  {
    auto stage = std::make_unique<stages::CurrentState>("current state");
    task.add(std::move(stage));
  }

  // ---- Stage 1: Move to grasp pose ----
  {
    auto stage = std::make_unique<stages::MoveTo>("move to grasp pose", arm_planner);
    stage->setGroup(ARM_GROUP);
    stage->setIKFrame("Link6");
    geometry_msgs::msg::PoseStamped ps;
    ps.header.frame_id = "base_link";
    ps.pose = target_pose;
    stage->setGoal(ps);
    task.add(std::move(stage));
  }

  try
  {
    task.enableIntrospection(true);
    task.init();
    if (!task.plan(5))
    {
      RCLCPP_ERROR(node_->get_logger(), "[MtcPlanner] moveToPose: planning failed");
      return false;
    }
    RCLCPP_INFO(node_->get_logger(), "[MtcPlanner] moveToPose: executing...");
    task.execute(*task.solutions().front());
    return true;
  }
  catch (const InitStageException &e)
  {
    RCLCPP_ERROR_STREAM(node_->get_logger(), "[MtcPlanner] moveToPose: stage init failed: " << e);
    return false;
  }
}

// Handles arm retreat to home only ***
bool MtcPlanner::moveToHome()
{
  Task task;
  task.stages()->setName("move_to_home");
  task.loadRobotModel(mtc_node_);

  auto arm_planner = std::make_shared<solvers::JointInterpolationPlanner>();

  // ---- Stage 0: Current state ----
  {
    auto stage = std::make_unique<stages::CurrentState>("current state");
    task.add(std::move(stage));
  }

  // ---- Stage 1: Retreat to home ----
  {
    auto stage = std::make_unique<stages::MoveTo>("retreat to home", arm_planner);
    stage->setGroup(ARM_GROUP);
    stage->setGoal(HOME_JOINTS);
    task.add(std::move(stage));
  }

  try
  {
    task.enableIntrospection(true);
    task.init();
    if (!task.plan(5))
    {
      RCLCPP_ERROR(node_->get_logger(), "[MtcPlanner] moveToHome: planning failed");
      return false;
    }
    RCLCPP_INFO(node_->get_logger(), "[MtcPlanner] moveToHome: executing...");
    task.execute(*task.solutions().front());
    return true;
  }
  catch (const InitStageException &e)
  {
    RCLCPP_ERROR_STREAM(node_->get_logger(), "[MtcPlanner] moveToHome: stage init failed: " << e);
    return false;
  }
}