#include "grasp_state_machine/mtc_planner.hpp"
#include <moveit/planning_scene/planning_scene.h>
#include <moveit/robot_state/robot_state.h>
#include <moveit/robot_trajectory/robot_trajectory.h>
#include <moveit/trajectory_processing/time_optimal_trajectory_generation.h>
#include <tf2_eigen/tf2_eigen.hpp>
#include <cmath>
#include <sstream>

// Stores pointer to state machine node from which it originated
MtcPlanner::MtcPlanner(const rclcpp::Node::SharedPtr &node, const std::atomic<bool> &stopped)
    : node_(node), stopped_(stopped)
{
  step_settle_s_ = node_->get_parameter("step_settle_s").as_double();
  max_wrist_turn_deg_ = node_->get_parameter("max_wrist_turn_deg").as_double();
  pregrasp_distance_m_ = node_->get_parameter("pregrasp_distance_m").as_double();
  mtc_node_ = std::make_shared<rclcpp::Node>(
      "mtc_planner_node",
      rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true));
  mtc_executor_ = std::make_shared<rclcpp::executors::SingleThreadedExecutor>();
  mtc_executor_->add_node(mtc_node_);
  mtc_spin_thread_ = std::thread([this]()
                                 { mtc_executor_->spin(); });
  move_group_ = std::make_shared<moveit::planning_interface::MoveGroupInterface>(mtc_node_, "rm_group");
}

// The standard MoveIt pick order (MTC pick-and-place tutorial), without the gripper stages: the
// gripper is driven by rm_driver topics from the state machine, not by MoveIt.
// The old single joint-space move bent the gripper's path into the box (CODE_AUDIT A4, T1.48).
bool MtcPlanner::approachGrasp(const geometry_msgs::msg::Pose &grasp_pose)
{
  Task task;
  task.stages()->setName("approach_grasp");
  task.loadRobotModel(mtc_node_);

  // Searches for a path around everything in the planning scene, the target included
  auto path_planner = std::make_shared<solvers::PipelinePlanner>(mtc_node_, "ompl");
  path_planner->setMaxVelocityScalingFactor(0.1);
  path_planner->setMaxAccelerationScalingFactor(0.1);
  // Moves grasp_frame in a straight line, keeping its orientation
  auto straight_planner = std::make_shared<solvers::CartesianPath>();
  straight_planner->setMaxVelocityScalingFactor(0.1);
  straight_planner->setMaxAccelerationScalingFactor(0.1);
  straight_planner->setStepSize(0.005);
  straight_planner->setMinFraction(1.0); // all of the straight line, or no move

  // Pre-grasp: back from the grasp along its approach. grasp_frame's -z is the approach
  // (anygrasp_to_grasp_frame.py), so back is +z.
  Eigen::Isometry3d grasp;
  tf2::fromMsg(grasp_pose, grasp);
  Eigen::Isometry3d pregrasp = grasp * Eigen::Translation3d(0.0, 0.0, pregrasp_distance_m_);

  // IK for the pre-grasp, starting from the current joints, so it lands on the nearest solution.
  // Given the pose, OMPL samples IK from random seeds and chose joint6 a full 360 deg turn away
  // in the simulated arm, the same as the flipped wrist on the real arm (2026-10-26)
  auto pregrasp_state = move_group_->getCurrentState(1.0);
  if (!pregrasp_state)
  {
    RCLCPP_ERROR(node_->get_logger(), "[MtcPlanner] approachGrasp: no current joint state");
    return false;
  }
  const auto *arm = pregrasp_state->getJointModelGroup(ARM_GROUP);
  if (!pregrasp_state->setFromIK(arm, pregrasp, "grasp_frame", 0.1))
  {
    RCLCPP_ERROR(node_->get_logger(), "[MtcPlanner] approachGrasp: no IK for the pre-grasp %.2f m back",
                 pregrasp_distance_m_);
    return false;
  }
  std::map<std::string, double> pregrasp_joints;
  for (const auto *joint : arm->getActiveJointModels())
    pregrasp_joints[joint->getName()] = pregrasp_state->getVariablePosition(joint->getFirstVariableIndex());

  task.add(std::make_unique<stages::CurrentState>("current state"));
  {
    auto stage = std::make_unique<stages::MoveTo>("to pre-grasp", path_planner);
    stage->setGroup(ARM_GROUP);
    stage->setGoal(pregrasp_joints);
    task.add(std::move(stage));
  }
  {
    // Only for the straight move: the arm links and the camera still may not touch the target
    auto stage = std::make_unique<stages::ModifyPlanningScene>("allow gripper contact");
    stage->allowCollisions(TARGET_ID, GRIPPER_LINKS, true);
    task.add(std::move(stage));
  }
  {
    auto stage = std::make_unique<stages::MoveTo>("straight in", straight_planner);
    stage->setGroup(ARM_GROUP);
    stage->setIKFrame("grasp_frame");
    geometry_msgs::msg::PoseStamped goal;
    goal.header.frame_id = "base_link";
    goal.pose = grasp_pose;
    stage->setGoal(goal);
    task.add(std::move(stage));
  }

  try
  {
    task.enableIntrospection(true);
    task.init();
    RCLCPP_INFO(node_->get_logger(), "[MtcPlanner] Planning to grasp: x=%.3f y=%.3f z=%.3f, pre-grasp %.2f m back",
                grasp_pose.position.x, grasp_pose.position.y, grasp_pose.position.z, pregrasp_distance_m_);
    if (!task.plan(5))
    {
      std::ostringstream why;
      task.explainFailure(why);
      const auto &q = grasp_pose.orientation;
      RCLCPP_ERROR(node_->get_logger(),
                   "[MtcPlanner] approachGrasp: planning failed, target q=(%.3f %.3f %.3f %.3f): %s",
                   q.x, q.y, q.z, q.w, why.str().c_str());
      return false;
    }
    // The planner takes any IK solution. A flipped wrist reaches the same pose with joint 4 and
    // joint 6 turned about 180 degrees, and swung the gripper through the object before the
    // target was in the scene (T1.45, 2026-10-26). Kept as a guard until T1.48 works at the arm.
    const auto &solution = *task.solutions().front();
    const auto &start = solution.start()->scene()->getCurrentState();
    const auto &end = solution.end()->scene()->getCurrentState();
    for (const char *joint : {"joint4", "joint5", "joint6"})
    {
      double turn_deg = std::abs(end.getVariablePosition(joint) - start.getVariablePosition(joint)) * 180.0 / M_PI;
      if (turn_deg > max_wrist_turn_deg_)
      {
        RCLCPP_WARN(node_->get_logger(), "[MtcPlanner] approachGrasp: refused, %s would turn %.0f deg (limit %.0f)",
                    joint, turn_deg, max_wrist_turn_deg_);
        return false;
      }
    }
    if (refuseIfStopped("approachGrasp"))
      return false;
    RCLCPP_INFO(node_->get_logger(), "[MtcPlanner] approachGrasp: executing...");
    auto result = task.execute(solution);
    if (result != moveit::core::MoveItErrorCode::SUCCESS)
    {
      RCLCPP_ERROR(node_->get_logger(), "[MtcPlanner] approachGrasp: execution failed, code %d", result.val);
      return false;
    }
    return true;
  }
  catch (const InitStageException &e)
  {
    RCLCPP_ERROR_STREAM(node_->get_logger(), "[MtcPlanner] approachGrasp: stage init failed: " << e);
    return false;
  }
}

bool MtcPlanner::addTarget(moveit_msgs::msg::CollisionObject target)
{
  target.id = TARGET_ID;
  target.operation = moveit_msgs::msg::CollisionObject::ADD;
  return psi_.applyCollisionObject(target);
}

// The gripper links may touch the attached target, so holding it is not a collision
bool MtcPlanner::attachTarget()
{
  moveit_msgs::msg::AttachedCollisionObject attached;
  attached.link_name = GRIPPER_LINKS.front();
  attached.object.id = TARGET_ID;
  attached.object.operation = moveit_msgs::msg::CollisionObject::ADD;
  attached.touch_links = GRIPPER_LINKS;
  return psi_.applyAttachedCollisionObject(attached);
}

// Detach, then remove from the world. Called at the start of every
// cycle, so a target left by a failed or stopped grasp never blocks the next one.
void MtcPlanner::removeTarget()
{
  // Only what is there: removing a missing object makes move_group log an error
  if (!psi_.getAttachedObjects({TARGET_ID}).empty())
  {
    moveit_msgs::msg::AttachedCollisionObject detach;
    detach.link_name = GRIPPER_LINKS.front();
    detach.object.id = TARGET_ID;
    detach.object.operation = moveit_msgs::msg::CollisionObject::REMOVE;
    psi_.applyAttachedCollisionObject(detach);
  }
  if (!psi_.getObjects({TARGET_ID}).empty())
  {
    moveit_msgs::msg::CollisionObject remove;
    remove.id = TARGET_ID;
    remove.operation = moveit_msgs::msg::CollisionObject::REMOVE;
    psi_.applyCollisionObject(remove);
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
  if (refuseIfStopped("moveToHome"))
    return false;
  move_group_->execute(plan);
  return true;
}

bool MtcPlanner::moveToReturn()
{
  move_group_->setJointValueTarget(RETURN_JOINTS);
  move_group_->setMaxVelocityScalingFactor(0.1);
  move_group_->setMaxAccelerationScalingFactor(0.1);
  moveit::planning_interface::MoveGroupInterface::Plan plan;
  if (move_group_->plan(plan) != moveit::core::MoveItErrorCode::SUCCESS)
  {
    RCLCPP_ERROR(node_->get_logger(), "[MtcPlanner] moveToReturn: planning failed");
    return false;
  }
  if (refuseIfStopped("moveToReturn"))
    return false;
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
  // The real arm is still settling just after the last step reports done, so a step planned from
  // that moment starts off where the arm really is and MoveIt rejects it (T1.24 3c, 2026-10-13)
  std::this_thread::sleep_for(std::chrono::duration<double>(step_settle_s_));
  move_group_->setStartStateToCurrentState();
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
  if (refuseIfStopped("moveCartesianStep"))
    return false;
  return (move_group_->execute(plan) == moveit::core::MoveItErrorCode::SUCCESS);
}

// Checked after planning, just before each execute: planning takes up to 5 s, and a stop that
// came in meanwhile must not be followed by the move (T1.38).
// ponytail: a stop landing between this check and MoveIt starting the move still lets that move
// start. The stop's own cancel (stopMotion) was sent before it, so it does not cancel it. The
// window is milliseconds. Close it with asyncExecute + a stop check if it ever shows up.
bool MtcPlanner::refuseIfStopped(const char *what)
{
  if (!stopped_)
    return false;
  RCLCPP_WARN(node_->get_logger(), "[MtcPlanner] %s: not sent, stopped. Press R in the e-stop pane to resume", what);
  return true;
}
