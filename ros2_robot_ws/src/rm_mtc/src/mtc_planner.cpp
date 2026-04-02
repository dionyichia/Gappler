#include "rm_mtc/mtc_planner.hpp"
#include <moveit/robot_trajectory/robot_trajectory.h>
#include <moveit/trajectory_processing/time_optimal_trajectory_generation.h>

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
  move_group_ = std::make_shared<moveit::planning_interface::MoveGroupInterface>(mtc_node_, "rm_group");
}

// *** CHANGED: replaces executeGrasp(), handles arm motion to target pose only ***
bool MtcPlanner::moveToPose(const geometry_msgs::msg::Pose &target_pose)
{
  Task task;
  task.stages()->setName("move_to_pose");
  task.loadRobotModel(mtc_node_);

  auto arm_planner = std::make_shared<solvers::JointInterpolationPlanner>();
  arm_planner->setMaxVelocityScalingFactor(0.1);
  arm_planner->setMaxAccelerationScalingFactor(0.1);

  // ---- Stage 0: Current state ----
  {
    auto stage = std::make_unique<stages::CurrentState>("current state");
    task.add(std::move(stage));
  }

  // ---- Stage 1: Move to grasp pose ----
  {
    auto stage = std::make_unique<stages::MoveTo>("move to grasp pose", arm_planner);
    stage->setGroup(ARM_GROUP);
    stage->setIKFrame("grasp_frame");
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
    RCLCPP_INFO(node_->get_logger(), "[MtcPlanner] Planning to pose: x=%.3f y=%.3f z=%.3f",
                target_pose.position.x, target_pose.position.y, target_pose.position.z);
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

// Handles arm retreat back to home pose
bool MtcPlanner::moveToHome()
{
  move_group_->setJointValueTarget(HOME_JOINTS);
  move_group_->setMaxVelocityScalingFactor(0.1);
  move_group_->setMaxAccelerationScalingFactor(0.1);
  moveit::planning_interface::MoveGroupInterface::Plan plan;
  if (move_group_->plan(plan) != moveit::core::MoveItErrorCode::SUCCESS)
  {
    RCLCPP_ERROR(node_->get_logger(), "[MtcPlanner] moveToHome: planning failed");
    return false;
  }
  move_group_->execute(plan);
  return true;
}

geometry_msgs::msg::PoseStamped MtcPlanner::getCurrentPose()
{
  return move_group_->getCurrentPose();
}

bool MtcPlanner::moveCartesianStep(const geometry_msgs::msg::Pose &goal_pose_base)
{
  move_group_->setMaxVelocityScalingFactor(0.1);
  move_group_->setMaxAccelerationScalingFactor(0.1);
  std::vector<geometry_msgs::msg::Pose> waypoints = {goal_pose_base};
  moveit_msgs::msg::RobotTrajectory trajectory;
  double fraction = move_group_->computeCartesianPath(waypoints, 0.01, 5.0, trajectory);
  if (fraction < 0.8)
  {
    RCLCPP_WARN(node_->get_logger(), "[MtcPlanner] Cartesian path only %.0f%% complete", fraction * 100);
    return false;
  }
  robot_trajectory::RobotTrajectory rt(move_group_->getRobotModel(), move_group_->getName());
  rt.setRobotTrajectoryMsg(*move_group_->getCurrentState(), trajectory);

  trajectory_processing::TimeOptimalTrajectoryGeneration totg;
  if (!totg.computeTimeStamps(rt, 0.1, 0.1))
  {
    RCLCPP_WARN(node_->get_logger(), "[MtcPlanner] Time parameterization failed");
    return false;
  }
  rt.getRobotTrajectoryMsg(trajectory);

  moveit::planning_interface::MoveGroupInterface::Plan plan;
  plan.trajectory_ = trajectory;
  return (move_group_->execute(plan) == moveit::core::MoveItErrorCode::SUCCESS);
}