#include <atomic>
#include <memory>
#include <thread>
#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <moveit/task_constructor/task.h>
#include <moveit/task_constructor/stages.h>
#include <moveit/task_constructor/solvers.h>
#include <moveit/move_group_interface/move_group_interface.h>
#include <moveit/planning_scene_interface/planning_scene_interface.h>
#include <moveit_msgs/msg/collision_object.hpp>
#include <moveit_task_constructor_msgs/msg/solution.hpp>

using namespace moveit::task_constructor;

class MtcPlanner
{
public:
  // stopped: the state machine's stop flag (T1.38). While it is set, no move is sent.
  MtcPlanner(const rclcpp::Node::SharedPtr &node, const std::atomic<bool> &stopped);

  ~MtcPlanner()
  {
    mtc_executor_->cancel();
    if (mtc_spin_thread_.joinable())
      mtc_spin_thread_.join();
  }
  // Moves the gripper to grasp_pose (base_link) or its 180 degree twin, whichever plans with less
  // joint travel (T1.51): a collision-free path to pregrasp_distance_m back along the approach,
  // then straight in (T1.48). Only the gripper may touch TARGET_ID.
  // Returns true on success, false on planning or execution failure.
  bool approachGrasp(const geometry_msgs::msg::Pose &grasp_pose);

  // The grasp target in MoveIt's planning scene (T1.48). add puts it in the world, attach moves
  // it onto the gripper after closing, remove takes it out of both. Each returns once applied.
  bool addTarget(moveit_msgs::msg::CollisionObject target);
  bool attachTarget();
  void removeTarget();

  // Moves arm back to the defined home joint configuration.
  // Returns true on success, false on planning or execution failure.
  bool moveToHome();
  bool moveToReturn();

  geometry_msgs::msg::PoseStamped getCurrentPose();

  bool moveCartesianStep(const geometry_msgs::msg::Pose &goal_pose_base);

  // Cancels the move in progress. Safe from another thread: it only publishes MoveIt's "stop" event.
  void stopMotion() { move_group_->stop(); }

private:
  rclcpp::Node::SharedPtr node_;
  rclcpp::Node::SharedPtr mtc_node_;
  std::shared_ptr<rclcpp::executors::SingleThreadedExecutor> mtc_executor_;
  std::shared_ptr<moveit::planning_interface::MoveGroupInterface> move_group_;
  std::thread mtc_spin_thread_;
  double step_settle_s_; // step_settle_s in grasp/grasp_config.yaml
  double max_wrist_turn_deg_; // max_wrist_turn_deg in grasp/grasp_config.yaml
  double pregrasp_distance_m_; // pregrasp_distance_m in grasp/grasp_config.yaml
  bool plan_only_; // plan_only in grasp/grasp_config.yaml
  // Made once, so a recorder that subscribed at start-up gets every plan. MTC's own /solution
  // publisher is made per Task and gone when approachGrasp returns, maybe before it is heard (T1.51)
  rclcpp::Publisher<moveit_task_constructor_msgs::msg::Solution>::SharedPtr solution_pub_;
  // The rest are the keys of the same name in grasp/grasp_config.yaml, section grasp_state_machine
  double max_velocity_scale_;           // arm_max_velocity_scale, every move
  double max_acceleration_scale_;       // arm_max_acceleration_scale, every move
  double straight_in_step_m_;           // straight_in_step_m
  int approach_plan_solutions_;         // approach_plan_solutions
  double pregrasp_ik_timeout_s_;        // pregrasp_ik_timeout_s
  double joint_state_wait_s_;           // joint_state_wait_s
  double cartesian_step_eef_step_m_;    // cartesian_step_eef_step_m
  double cartesian_step_jump_threshold_; // cartesian_step_jump_threshold
  double cartesian_step_min_fraction_;  // cartesian_step_min_fraction
  moveit::planning_interface::PlanningSceneInterface psi_;
  const std::atomic<bool> &stopped_;

  bool refuseIfStopped(const char *what);
  // One pose's plan: IK at the pre-grasp (P2), path and straight in (P3-P4), wrist turn (P6).
  // Null if any fails. travel is the plan's joint change, summed over every joint and step, radians.
  std::unique_ptr<Task> planApproach(const geometry_msgs::msg::Pose &grasp_pose, const char *name, double &travel);

  const std::string ARM_GROUP = "rm_group";
  // The target's id in the planning scene. The detector publishes it under this id too.
  const std::string TARGET_ID = "grasp_target";
  // The links that may touch the target: the gripper, not the arm or the camera. The SRDF has no
  // gripper group (rm_65_description.srdf), so they are listed here. The target attaches to the first.
  const std::vector<std::string> GRIPPER_LINKS = {
      "gripper_base_link", "gripper_Link1", "gripper_Link2", "gripper_Link3", "gripper_Link4"};

  // Home pose, home_joints_rad in grasp/grasp_config.yaml (validated on the real arm, T1.7)
  std::map<std::string, double> HOME_JOINTS;

  // Return pose: the home pose for now (Dion, 2026-10-05). HOME is the only pose
  // validated on the real arm (T1.7), and a real hand-to-user pose is future work.
  // The old row (joint3 2.3000, never run on the real arm) is in git history.
  std::map<std::string, double> RETURN_JOINTS;
};
