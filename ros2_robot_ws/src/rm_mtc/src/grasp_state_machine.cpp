#include <chrono>
#include <condition_variable>
#include <deque>
#include <future>
#include <mutex>
#include <queue>
#include <thread>
#include <cmath>

#include <moveit/planning_scene_interface/planning_scene_interface.h>
#include <moveit_msgs/msg/collision_object.hpp>
#include <shape_msgs/msg/solid_primitive.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/point_stamped.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/vector3.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/string.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <rm_ros_interfaces/msg/gripperpick.hpp>
#include <rm_ros_interfaces/msg/gripperset.hpp>
#include <rm_ros_interfaces/msg/grasp_candidate_array.hpp>
#include "rm_mtc/mtc_planner.hpp"

// ===========================================================================
// Tuning constants
// ===========================================================================
static constexpr double APPROACH_STEP_M = 0.04;
static constexpr double APPROACH_STEP_FINAL = 0.10;
static constexpr int MAX_APPROACH_STEPS = 50;
static constexpr double EXECUTE_DEPTH_THRESH_M = 0.18;
static constexpr double FINAL_EXEC_THRESH_M = 0.25;
static constexpr double CENTROID_TARGET_OFFSET_X = 55.0;
static constexpr double CENTROID_TARGET_OFFSET_Y = 0.0;
static constexpr double MIN_APPROACH_ANGLE_DEG = 20.0;
static constexpr double MAX_ORIENT_STEP_DEG = 5.0;
static constexpr bool USE_SIMPLE_EXECUTE = true;
static constexpr bool USE_SLERP_EXECUTE = false;

// Stability criterion
static constexpr int STABILITY_N_FRAMES = 5;
static constexpr double STABILITY_TRANS_MM = 15.0;
static constexpr double STABILITY_ROT_DEG = 10.0;

// ===========================================================================
// State definitions
// ===========================================================================
enum class State
{
  IDLE,
  SELECTING,
  EXECUTING
};

static std::string stateToString(State s)
{
  switch (s)
  {
  case State::IDLE:
    return "IDLE";
  case State::SELECTING:
    return "SELECTING";
  case State::EXECUTING:
    return "EXECUTING";
  }
  return "UNKNOWN";
}

// ===========================================================================
// Math helpers
// ===========================================================================
static double quatDotAbs(const geometry_msgs::msg::Quaternion &a,
                         const geometry_msgs::msg::Quaternion &b)
{
  return std::abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w);
}

static double angleBetweenQuats(const geometry_msgs::msg::Quaternion &a,
                                const geometry_msgs::msg::Quaternion &b)
{
  return 2.0 * std::acos(std::min(1.0, quatDotAbs(a, b))) * 180.0 / M_PI;
}

static double transDist(const geometry_msgs::msg::Point &a,
                        const geometry_msgs::msg::Point &b)
{
  double dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
  return std::sqrt(dx * dx + dy * dy + dz * dz) * 1000.0; // metres → mm
}

static double approachAngleDeg(const geometry_msgs::msg::Quaternion &q)
{
  double az = 1 - 2 * (q.x * q.x + q.y * q.y);
  return std::asin(std::abs(az)) * 180.0 / M_PI;
}

// ===========================================================================
// GraspStateMachine node
// ===========================================================================
class GraspStateMachine : public rclcpp::Node
{
public:
  static std::shared_ptr<GraspStateMachine> create()
  {
    auto node = std::shared_ptr<GraspStateMachine>(new GraspStateMachine());
    node->mtc_planner_ = std::make_shared<MtcPlanner>(node);
    node->worker_thread_ = std::thread(&GraspStateMachine::workerLoop, node.get());
    return node;
  }

  ~GraspStateMachine()
  {
    {
      std::lock_guard<std::mutex> lock(queue_mutex_);
      shutdown_ = true;
    }
    queue_cv_.notify_all();
    if (worker_thread_.joinable())
      worker_thread_.join();
  }

private:
  // =========================================================================
  // Constructor — ROS wiring only
  // =========================================================================
  GraspStateMachine()
      : Node("grasp_state_machine",
             rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true)),
        tf_buffer_(this->get_clock()),
        tf_listener_(tf_buffer_),
        state_(State::IDLE),
        shutdown_(false)
  {
    camera_info_sub_ = this->create_subscription<sensor_msgs::msg::CameraInfo>(
        "/camera/camera/color/camera_info", 1,
        std::bind(&GraspStateMachine::cameraInfoCallback, this, std::placeholders::_1));

    grasp_sub_ = this->create_subscription<rm_ros_interfaces::msg::GraspCandidateArray>(
        "/grasp_candidates", 10,
        std::bind(&GraspStateMachine::graspCallback, this, std::placeholders::_1));

    centroid_sub_ = this->create_subscription<geometry_msgs::msg::PointStamped>(
        "/object_centroid_2d", 10,
        std::bind(&GraspStateMachine::centroidCallback, this, std::placeholders::_1));

    gripper_position_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperset>(
        "/rm_driver/set_gripper_position_cmd", 10);

    gripper_pick_on_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperpick>(
        "/rm_driver/set_gripper_pick_on_cmd", 10);

    pipeline_state_pub_ = this->create_publisher<std_msgs::msg::String>(
        "/pipeline_state", 10);

    RCLCPP_INFO(this->get_logger(), "Grasp state machine constructed");
  }

  // =========================================================================
  // Callbacks
  // =========================================================================
  void cameraInfoCallback(const sensor_msgs::msg::CameraInfo::SharedPtr msg)
  {
    if (intrinsics_received_)
      return;
    fx_ = msg->k[0];
    fy_ = msg->k[4];
    image_cx_ = msg->k[2];
    image_cy_ = msg->k[5];
    intrinsics_received_ = true;
    RCLCPP_INFO(this->get_logger(),
                "Intrinsics: fx=%.2f fy=%.2f cx=%.2f cy=%.2f", fx_, fy_, image_cx_, image_cy_);
    camera_info_sub_.reset();
  }

  void graspCallback(const rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg)
  {
    if (state_ != State::EXECUTING || msg->grasps.empty())
      return;
    {
      std::lock_guard<std::mutex> lock(queue_mutex_);
      candidate_queue_.push(msg);
    }
    queue_cv_.notify_one();
  }

  void centroidCallback(const geometry_msgs::msg::PointStamped::SharedPtr msg)
  {
    std::lock_guard<std::mutex> lock(centroid_mutex_);
    latest_centroid_ = *msg;
    has_centroid_ = true;
    queue_cv_.notify_one();
  }

  // =========================================================================
  // State publisher
  // =========================================================================
  void publishState(State s)
  {
    state_ = s;
    std_msgs::msg::String msg;
    msg.data = stateToString(s);
    pipeline_state_pub_->publish(msg);
    RCLCPP_INFO(this->get_logger(), "State → %s", msg.data.c_str());
  }

  // =========================================================================
  // Gripper helpers
  // =========================================================================
  void openGripper()
  {
    rm_ros_interfaces::msg::Gripperset msg;
    msg.position = 1000;
    msg.block = false;
    gripper_position_pub_->publish(msg);
    std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    RCLCPP_INFO(this->get_logger(), "Gripper opened");
  }

  void closeGripper()
  {
    rm_ros_interfaces::msg::Gripperpick msg;
    msg.speed = 200;
    msg.force = 150;
    msg.block = false;
    gripper_pick_on_pub_->publish(msg);
    std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    RCLCPP_INFO(this->get_logger(), "Gripper closed");
  }

  // =========================================================================
  // TF2 helper
  // =========================================================================
  bool transformToBase(const geometry_msgs::msg::Pose &pose_in,
                       geometry_msgs::msg::Pose &pose_out)
  {
    geometry_msgs::msg::PoseStamped stamped_in, stamped_out;
    stamped_in.header.frame_id = "camera_color_optical_frame";
    stamped_in.header.stamp = this->now();
    stamped_in.pose = pose_in;
    try
    {
      tf_buffer_.transform(stamped_in, stamped_out, "base_link", tf2::durationFromSec(1.0));
      pose_out = stamped_out.pose;
      return true;
    }
    catch (const tf2::TransformException &ex)
    {
      RCLCPP_WARN(this->get_logger(), "TF2 failed: %s", ex.what());
      return false;
    }
  }

  // =========================================================================
  // Stability tracker
  // =========================================================================
  void resetStability() { stability_window_.clear(); }

  bool checkStability(const geometry_msgs::msg::Pose &candidate,
                      geometry_msgs::msg::Pose &stable_pose)
  {
    stability_window_.push_back(candidate);
    if ((int)stability_window_.size() > STABILITY_N_FRAMES)
      stability_window_.pop_front();
    if ((int)stability_window_.size() < STABILITY_N_FRAMES)
      return false;

    const auto &ref = stability_window_.front();
    for (int i = 1; i < STABILITY_N_FRAMES; ++i)
    {
      if (transDist(stability_window_[i].position, ref.position) > STABILITY_TRANS_MM)
        return false;
      if (angleBetweenQuats(stability_window_[i].orientation, ref.orientation) > STABILITY_ROT_DEG)
        return false;
    }
    stable_pose = stability_window_.back();
    return true;
  }

  // =========================================================================
  // Safety walls
  // =========================================================================
  void addSafetyWalls()
  {
    std::this_thread::sleep_for(std::chrono::seconds(3));
    moveit::planning_interface::PlanningSceneInterface psi;

    struct Wall
    {
      std::string id;
      double cx, cy, cz, sx, sy, sz;
    };
    const double T = 0.03;
    const std::vector<Wall> walls = {
        {"+x_wall", 0.15 + T / 2, 0.0, 0.5, T, 0.60 + T, 1.0},
        {"+y_wall", 0.0, 0.30 + T / 2, 0.5, 2.0, T, 1.0},
        {"-y_wall", 0.0, -0.30 - T / 2, 0.5, 2.0, T, 1.0},
        {"table", -0.425, 0.0, 0.18, 0.75, 0.75, T},
    };

    std::vector<moveit_msgs::msg::CollisionObject> objs;
    for (const auto &w : walls)
    {
      moveit_msgs::msg::CollisionObject obj;
      obj.header.frame_id = "base_link";
      obj.id = w.id;
      obj.operation = moveit_msgs::msg::CollisionObject::ADD;
      shape_msgs::msg::SolidPrimitive box;
      box.type = shape_msgs::msg::SolidPrimitive::BOX;
      box.dimensions = {w.sx, w.sy, w.sz};
      geometry_msgs::msg::Pose pose;
      pose.position.x = w.cx;
      pose.position.y = w.cy;
      pose.position.z = w.cz;
      pose.orientation.w = 1.0;
      obj.primitives.push_back(box);
      obj.primitive_poses.push_back(pose);
      objs.push_back(obj);
    }

    while (rclcpp::ok())
    {
      psi.applyCollisionObjects(objs);
      auto known = psi.getKnownObjectNames();
      bool all_added = std::all_of(walls.begin(), walls.end(), [&](const Wall &w)
                                   { return std::find(known.begin(), known.end(), w.id) != known.end(); });
      if (all_added)
      {
        RCLCPP_INFO(this->get_logger(), "Safety walls added");
        break;
      }
      RCLCPP_WARN(this->get_logger(), "Waiting for planning scene to accept safety walls...");
      std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
  }

  void homeWithRetry()
  {
    while (!mtc_planner_->moveToHome())
    {
      if (shutdown_)
        return;
      RCLCPP_WARN(this->get_logger(), "Homing failed, retrying...");
      std::this_thread::sleep_for(std::chrono::seconds(1));
    }
  }

  void returnWithRetry()
  {
    while (!mtc_planner_->moveToReturn())
    {
      if (shutdown_)
        return;
      RCLCPP_WARN(this->get_logger(), "Return failed, retrying...");
      std::this_thread::sleep_for(std::chrono::seconds(1));
    }
  }
  // =========================================================================
  // SELECTING — iterative approach step (called once per loop iteration)
  // =========================================================================
  // Returns false if the step could not be computed or executed.
  bool selectingStep()
  {
    if (!intrinsics_received_)
      return true; // not ready yet, silently skip

    auto current_pose_stamped = mtc_planner_->getCurrentPose();
    geometry_msgs::msg::PoseStamped current_pose_cam;
    try
    {
      tf_buffer_.transform(current_pose_stamped, current_pose_cam,
                           "camera_color_optical_frame", tf2::durationFromSec(0.1));
    }
    catch (const tf2::TransformException &ex)
    {
      RCLCPP_WARN(this->get_logger(), "SELECTING: EEF transform failed: %s", ex.what());
      return false;
    }

    geometry_msgs::msg::PoseStamped goal_pose_cam = current_pose_cam;
    {
      std::lock_guard<std::mutex> lock(centroid_mutex_);
      double px_err_x = latest_centroid_.point.x - (image_cx_ + CENTROID_TARGET_OFFSET_X);
      double px_err_y = latest_centroid_.point.y - (image_cy_ + CENTROID_TARGET_OFFSET_Y);
      double depth = latest_centroid_.point.z;

      double lateral_x = (px_err_x / fx_) * depth;
      double lateral_y = (px_err_y / fy_) * depth;
      double dz = APPROACH_STEP_M;

      double magnitude = std::sqrt(lateral_x * lateral_x + lateral_y * lateral_y + dz * dz);
      double scale = APPROACH_STEP_M / magnitude;

      goal_pose_cam.pose.position.x += lateral_x * scale;
      goal_pose_cam.pose.position.y += lateral_y * scale;
      goal_pose_cam.pose.position.z += dz * scale;
    }

    geometry_msgs::msg::PoseStamped goal_pose_base;
    try
    {
      tf_buffer_.transform(goal_pose_cam, goal_pose_base, "base_link", tf2::durationFromSec(0.1));
    }
    catch (const tf2::TransformException &ex)
    {
      RCLCPP_WARN(this->get_logger(), "SELECTING: goal transform failed: %s", ex.what());
      return false;
    }

    if (!mtc_planner_->moveCartesianStep(goal_pose_base.pose))
    {
      RCLCPP_WARN(this->get_logger(), "SELECTING: Cartesian step failed");
      return false;
    }
    return true;
  }

  // =========================================================================
  // Slerp helper (used by executingStep when USE_SLERP_EXECUTE = true)
  // =========================================================================
  static geometry_msgs::msg::Quaternion slerpQuat(
      const geometry_msgs::msg::Quaternion &q0,
      const geometry_msgs::msg::Quaternion &q1,
      double t)
  {
    double dot = q0.x * q1.x + q0.y * q1.y + q0.z * q1.z + q0.w * q1.w;
    geometry_msgs::msg::Quaternion q1s = q1;
    if (dot < 0.0)
    {
      q1s.x = -q1.x;
      q1s.y = -q1.y;
      q1s.z = -q1.z;
      q1s.w = -q1.w;
      dot = -dot;
    }
    dot = std::min(1.0, dot);
    double theta = std::acos(dot);
    if (theta < 1e-6)
      return q0;
    double s0 = std::sin((1 - t) * theta) / std::sin(theta);
    double s1 = std::sin(t * theta) / std::sin(theta);
    geometry_msgs::msg::Quaternion out;
    out.x = s0 * q0.x + s1 * q1s.x;
    out.y = s0 * q0.y + s1 * q1s.y;
    out.z = s0 * q0.z + s1 * q1s.z;
    out.w = s0 * q0.w + s1 * q1s.w;
    return out;
  }

  // =========================================================================
  // EXECUTING — iterative candidate evaluation step (called once per loop iteration)
  // Returns true when execution is complete (success or unrecoverable failure).
  // =========================================================================
  bool executingStep(bool &pose_locked, geometry_msgs::msg::Pose &stable_pose_base)
  {
    // --- Wait for a detection candidate (3s timeout) ---
    rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg;
    {
      std::unique_lock<std::mutex> lock(queue_mutex_);
      bool got = queue_cv_.wait_for(lock, std::chrono::seconds(3),
                                    [this]
                                    { return !candidate_queue_.empty() || shutdown_; });
      if (shutdown_)
        return true;
      if (!got || candidate_queue_.empty())
      {
        RCLCPP_WARN(this->get_logger(), "EXECUTING: no candidates received — aborting");
        return true; // signal done, return to IDLE
      }
      // Drain stale candidates, keep latest
      while (!candidate_queue_.empty())
      {
        msg = candidate_queue_.front();
        candidate_queue_.pop();
      }
    }

    // --- Pick best candidate passing approach angle check ---
    geometry_msgs::msg::Pose best_pose_cam;
    geometry_msgs::msg::Pose best_pose_base;
    bool found_valid = false;
    for (const auto &candidate : msg->grasps)
    {
      geometry_msgs::msg::Pose pose_base;
      if (!transformToBase(candidate.pose, pose_base))
        continue;
      if (approachAngleDeg(pose_base.orientation) < MIN_APPROACH_ANGLE_DEG)
      {
        RCLCPP_DEBUG(this->get_logger(), "Candidate rejected: angle %.1f° < %.1f°",
                     approachAngleDeg(pose_base.orientation), MIN_APPROACH_ANGLE_DEG);
        continue;
      }
      found_valid = true;
      best_pose_base = pose_base;
      break;
    }

    if (!found_valid)
    {
      RCLCPP_WARN(this->get_logger(), "EXECUTING: no candidate passed approach angle check");
      resetStability();
      return false; // keep looping
    }

    // // --- Transform best candidate to base_link ---

    // if (!transformToBase(best_pose_cam, best_pose_base))
    // {
    //   resetStability();
    //   return false;
    // }

    // --- Stability check ---
    if (!pose_locked && checkStability(best_pose_base, stable_pose_base))
    {
      RCLCPP_INFO(this->get_logger(), "EXECUTING: pose stable — locking target");
      pose_locked = true;
    }

    // --- Guard: check depth ---
    double object_depth;
    {
      std::lock_guard<std::mutex> lock(centroid_mutex_);
      if (!has_centroid_)
      {
        RCLCPP_WARN(this->get_logger(), "EXECUTING: no centroid available");
        return false;
      }
      object_depth = latest_centroid_.point.z;
    }

    // --- Final execute: pose locked ---
    if (pose_locked)
    {
      geometry_msgs::msg::Pose exec_pose = stable_pose_base;

      // Optional: slerp orientation from current toward target
      if (USE_SLERP_EXECUTE)
      {
        auto cur = mtc_planner_->getCurrentPose();
        double full_angle = angleBetweenQuats(cur.pose.orientation, stable_pose_base.orientation);
        double t = (full_angle > 1e-3) ? std::min(1.0, MAX_ORIENT_STEP_DEG / full_angle) : 1.0;
        exec_pose.orientation = slerpQuat(cur.pose.orientation, stable_pose_base.orientation, t);
      }

      RCLCPP_INFO(this->get_logger(),
                  "EXECUTING: pose locked, depth=%.3fm — executing final Cartesian move%s",
                  object_depth, USE_SLERP_EXECUTE ? " (slerp)" : "");
      if (mtc_planner_->moveToPose(exec_pose))
      {
        RCLCPP_INFO(this->get_logger(), "EXECUTING: Cartesian move succeeded");
        closeGripper();
      }
      else
      {
        RCLCPP_WARN(this->get_logger(), "EXECUTING: Cartesian move failed — retreating");
        auto cur = mtc_planner_->getCurrentPose();
        geometry_msgs::msg::Pose fallback = cur.pose;
        fallback.position.z += APPROACH_STEP_M;
        fallback.position.x += APPROACH_STEP_M;
        mtc_planner_->moveCartesianStep(fallback);
        resetStability();
        pose_locked = false;
        return false; // retry
      }
      return true; // done
    }

    return false; // keep looping
  }

  // =========================================================================
  // EXECUTING (simple) — just close gripper
  // =========================================================================
  void executingSimple()
  {

    // mtc_planner_->moveCartesianStep(final_pose_base.pose);
    closeGripper();
  }

  // =========================================================================
  // Worker loop — main state machine
  // =========================================================================
  void workerLoop()
  {
    // --- Startup ---
    std::this_thread::sleep_for(std::chrono::seconds(2));
    addSafetyWalls();
    homeWithRetry();
    publishState(State::IDLE);

    // -----------------------------------------------------------------------
    // DEBUG FLAG — set true to skip the main loop entirely
    // -----------------------------------------------------------------------
    if (debug_flag_)
    {
      RCLCPP_WARN(this->get_logger(), "debug_flag_ is set — worker loop halted");
      return;
    }
    // -----------------------------------------------------------------------

    while (true)
    {
      // =====================================================================
      // IDLE — wait for object detection
      // =====================================================================
      has_centroid_ = false;
      {
        std::unique_lock<std::mutex> lock(centroid_mutex_);
        queue_cv_.wait(lock, [this]
                       { return has_centroid_ || shutdown_; });
        if (shutdown_)
          return;
      }

      // Re-home beore each approach cycle
      homeWithRetry();
      // =====================================================================
      // SELECTING — approach object using 2D centroid
      // =====================================================================
      publishState(State::SELECTING);

      bool transition_to_executing = false;
      for (int steps = 0; steps < MAX_APPROACH_STEPS; ++steps)
      {
        double object_depth;
        {
          // auto age = this->now() - latest_centroid_.header.stamp;
          // if (age > rclcpp::Duration::from_seconds(1.0))
          // {
          //   RCLCPP_WARN(this->get_logger(), "SELECTING: centroid lost — returning to IDLE");
          //   break;
          // }
          object_depth = latest_centroid_.point.z;
        }

        if (object_depth < EXECUTE_DEPTH_THRESH_M)
        {
          RCLCPP_INFO(this->get_logger(),
                      "SELECTING: object at %.3fm — transitioning to EXECUTING", object_depth);
          transition_to_executing = true;
          break;
        }
        if (!selectingStep())
        {
          RCLCPP_WARN(this->get_logger(), "SELECTING: step failed — returning to IDLE");
          break;
        }
      }

      if (!transition_to_executing)
      {
        continue;
      }
      // ==================================================================
      // EXECUTING
      // ==================================================================
      publishState(State::EXECUTING);
      {
        std::lock_guard<std::mutex> lock(centroid_mutex_);
        centroid_snapshot_ = latest_centroid_;
      }
      openGripper();

      if (USE_SIMPLE_EXECUTE)
      {
        // Compute final target from snapshot
        auto current_pose_stamped = mtc_planner_->getCurrentPose();
        geometry_msgs::msg::PoseStamped current_pose_cam;

        // LOGICAL ERROR: missing try/catch — this transform can throw
        // tf2::TransformException but is unguarded here, unlike selectingStep()
        // which wraps the same call in try/catch
        tf_buffer_.transform(current_pose_stamped, current_pose_cam,
                             "camera_color_optical_frame", tf2::durationFromSec(0.1));

        double px_err_x = centroid_snapshot_.point.x - (image_cx_ + CENTROID_TARGET_OFFSET_X);
        double px_err_y = centroid_snapshot_.point.y - (image_cy_ + CENTROID_TARGET_OFFSET_Y);
        double depth = centroid_snapshot_.point.z;
        double lateral_x = (px_err_x / fx_) * depth;
        double lateral_y = (px_err_y / fy_) * depth;
        double dz = APPROACH_STEP_FINAL;
        double magnitude = std::sqrt(lateral_x * lateral_x + lateral_y * lateral_y + dz * dz);
        double scale = APPROACH_STEP_FINAL / magnitude;

        geometry_msgs::msg::PoseStamped goal_pose_cam = current_pose_cam;
        goal_pose_cam.pose.position.x += lateral_x * scale;
        goal_pose_cam.pose.position.y += lateral_y * scale;
        goal_pose_cam.pose.position.z += dz * scale;

        geometry_msgs::msg::PoseStamped goal_pose_base;

        // LOGICAL ERROR: same issue — unguarded transform, should be try/catch
        tf_buffer_.transform(goal_pose_cam, goal_pose_base, "base_link", tf2::durationFromSec(0.1));

        // HARDCODING BRITTLE FIX: overwrite goal pose z value with current z value
        // to prevent the planner from trying to move down into the table
        goal_pose_base.pose.position.z = current_pose_stamped.pose.position.z;

        // LOGICAL ERROR: return value of moveCartesianStep ignored —
        // executingSimple() will run even if the Cartesian step failed
        if (!mtc_planner_->moveCartesianStep(goal_pose_base.pose))
        {
          RCLCPP_WARN(this->get_logger(), "EXECUTING: final Cartesian step failed — aborting");
          return; // exit worker loop, effectively halting the node
        }
        executingSimple();
        RCLCPP_INFO(this->get_logger(), "Object grasped successfully");
        returnWithRetry();
        return;
      }
      else
      {
        bool pose_locked = false;
        geometry_msgs::msg::Pose stable_pose_base;
        resetStability();

        bool executing_done = false;
        while (!executing_done)
          executing_done = executingStep(pose_locked, stable_pose_base);
      }
      // =================================================================

      // =====================================================================
      // Return to IDLE
      // =====================================================================
      RCLCPP_INFO(this->get_logger(), "Cycle complete — returning to IDLE");
      homeWithRetry();
      publishState(State::IDLE);
    }
  }
  // =========================================================================
  // Members
  // =========================================================================

  // ROS interfaces
  rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::SharedPtr camera_info_sub_;
  rclcpp::Subscription<rm_ros_interfaces::msg::GraspCandidateArray>::SharedPtr grasp_sub_;
  rclcpp::Subscription<geometry_msgs::msg::PointStamped>::SharedPtr centroid_sub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperset>::SharedPtr gripper_position_pub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperpick>::SharedPtr gripper_pick_on_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pipeline_state_pub_;

  // TF2
  tf2_ros::Buffer tf_buffer_;
  tf2_ros::TransformListener tf_listener_;

  // Camera intrinsics
  double fx_ = 0.0, fy_ = 0.0, image_cx_ = 0.0, image_cy_ = 0.0;
  bool intrinsics_received_ = false;

  // State
  State state_;

  // Motion planner
  std::shared_ptr<MtcPlanner> mtc_planner_;

  // Centroid (shared with callbacks)
  geometry_msgs::msg::PointStamped latest_centroid_;
  bool has_centroid_ = false;
  std::mutex centroid_mutex_;
  geometry_msgs::msg::PointStamped centroid_snapshot_;

  // Grasp candidate queue (shared with callbacks)
  std::queue<rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr> candidate_queue_;
  std::mutex queue_mutex_;
  std::condition_variable queue_cv_;

  // Worker thread
  std::thread worker_thread_;
  bool shutdown_;

  // Stability window
  std::deque<geometry_msgs::msg::Pose> stability_window_;

  // Flags
  bool debug_flag_ = false;
  bool grasped_ = false;
};

// ===========================================================================
// Main
// ===========================================================================
int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = GraspStateMachine::create();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}