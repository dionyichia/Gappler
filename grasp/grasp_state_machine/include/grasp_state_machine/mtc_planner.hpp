#include <atomic>
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
  // Moves the gripper to grasp_pose (base_link): a collision-free path to pregrasp_distance_m
  // back along the approach, then straight in (T1.48). Only the gripper may touch TARGET_ID.
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
  moveit::planning_interface::PlanningSceneInterface psi_;
  const std::atomic<bool> &stopped_;

  bool refuseIfStopped(const char *what);

  const std::string ARM_GROUP = "rm_group";
  // The target's id in the planning scene. The detector publishes it under this id too.
  const std::string TARGET_ID = "grasp_target";
  // The links that may touch the target: the gripper, not the arm or the camera. The SRDF has no
  // gripper group (rm_65_description.srdf), so they are listed here. The target attaches to the first.
  const std::vector<std::string> GRIPPER_LINKS = {
      "gripper_base_link", "gripper_Link1", "gripper_Link2", "gripper_Link3", "gripper_Link4"};

  // Home pose joint values (radians)
  // Validated on the real arm 2026-09-23 (T1.7): commanded one joint at a time through
  // /rm_driver/movej_cmd, the arm reached every joint within 0.0004 rad (0.02 deg) of
  // these values, so they stand unchanged. The tool ends up in front of the arm's base,
  // which was checked and accepted at the robot. Evidence:
  // adb5466:docs/dion_docs/T1.7_FIRST_COMMANDED_MOTION.md
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
