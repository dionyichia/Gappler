#include <chrono>
#include <condition_variable>
#include <deque>
#include <moveit/planning_scene_interface/planning_scene_interface.h>
#include <moveit_msgs/msg/collision_object.hpp>
#include <shape_msgs/msg/solid_primitive.hpp>
#include <future>
#include <mutex>
#include <queue>
#include <thread>
#include <cmath>

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

// ---------------------------------------------------------------------------
// Tuning constants
// ---------------------------------------------------------------------------
static constexpr double APPROACH_STEP_M = 0.04;
static constexpr int MAX_APPROACH_STEPS = 50;
static constexpr double EXECUTE_DEPTH_THRESH_M = 0.2; // SELECTING → EXECUTING
static constexpr double FINAL_EXEC_THRESH_M = 0.2;    // final Cartesian execute
static constexpr double CENTROID_TARGET_OFFSET_X = 25.0;
static constexpr double CENTROID_TARGET_OFFSET_Y = 40.0;
static constexpr double MIN_APPROACH_ANGLE_DEG = 30.0; // min angle from horizontal
static constexpr double MAX_ORIENT_STEP_DEG = 5.0;     // max orientation change per step
static constexpr bool USE_SIMPLE_EXECUTE = true;

// Stability criterion
static constexpr int STABILITY_N_FRAMES = 2;       // consecutive agreeing frames
static constexpr double STABILITY_TRANS_MM = 20.0; // mm
static constexpr double STABILITY_ROT_DEG = 10.0;  // degrees

// ---------------------------------------------------------------------------
// State definitions
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
static double quatDotAbs(const geometry_msgs::msg::Quaternion &a,
                         const geometry_msgs::msg::Quaternion &b)
{
  double d = a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;
  return std::abs(d);
}

static double angleBetweenQuats(const geometry_msgs::msg::Quaternion &a,
                                const geometry_msgs::msg::Quaternion &b)
{
  double dot = quatDotAbs(a, b);
  dot = std::min(1.0, dot);
  return 2.0 * std::acos(dot) * 180.0 / M_PI;
}

static double transDist(const geometry_msgs::msg::Point &a,
                        const geometry_msgs::msg::Point &b)
{
  double dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
  return std::sqrt(dx * dx + dy * dy + dz * dz) * 1000.0; // metres → mm
}

// Approach vector angle from horizontal (in base_link frame).
// Returns degrees above horizontal. Grasps approaching into a table
// should have a significant downward (negative Z in base_link) component.
static double approachAngleDeg(const geometry_msgs::msg::Quaternion &q)
{
  // Rotate unit Z vector by quaternion to get approach direction
  double qx = q.x, qy = q.y;
  double az = 1 - 2 * (qx * qx + qy * qy);
  // Angle from horizontal = arcsin(|az|)
  return std::asin(std::abs(az)) * 180.0 / M_PI;
}

/*
// Slerp quaternion: interpolate from q0 toward q1 by fraction t
static geometry_msgs::msg::Quaternion slerpQuat(
    const geometry_msgs::msg::Quaternion &q0,
    const geometry_msgs::msg::Quaternion &q1,
    double t)
{
  double dot = q0.x * q1.x + q0.y * q1.y + q0.z * q1.z + q0.w * q1.w;
  // Use shortest path
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
*/

// ---------------------------------------------------------------------------
// GraspStateMachine node
// ---------------------------------------------------------------------------
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
  GraspStateMachine()
      : Node("grasp_state_machine",
             rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true)),
        state_(State::IDLE),
        tf_buffer_(this->get_clock()),
        tf_listener_(tf_buffer_),
        shutdown_(false)
  {
    camera_info_sub_ = this->create_subscription<sensor_msgs::msg::CameraInfo>(
        "/camera/camera/color/camera_info", 1,
        std::bind(&GraspStateMachine::cameraInfoCallback, this, std::placeholders::_1));

    // Only accept candidates during EXECUTING
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

    RCLCPP_INFO(this->get_logger(), "Grasp state machine ready. State: IDLE");
  }

  // ---------------------------------------------------------------------------
  // CameraInfo — one-time latch
  // ---------------------------------------------------------------------------
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
                "Intrinsics: fx=%.2f fy=%.2f cx=%.2f cy=%.2f",
                fx_, fy_, image_cx_, image_cy_);
    camera_info_sub_.reset();
  }

  // ---------------------------------------------------------------------------
  // State publisher
  // ---------------------------------------------------------------------------
  void publishState(State s)
  {
    state_ = s;
    std_msgs::msg::String msg;
    msg.data = stateToString(s);
    pipeline_state_pub_->publish(msg);
    RCLCPP_INFO(this->get_logger(), "State → %s", msg.data.c_str());
  }

  // ---------------------------------------------------------------------------
  // Callbacks
  // ---------------------------------------------------------------------------
  void graspCallback(const rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg)
  {
    if (state_ != State::EXECUTING)
      return;
    if (msg->grasps.empty())
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

  // ---------------------------------------------------------------------------
  // Stability check
  // ---------------------------------------------------------------------------
  // Adds candidate to rolling window and returns true + best pose if stable
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

    // Use most recent pose as the stable target
    stable_pose = stability_window_.back();
    return true;
  }

  void resetStability() { stability_window_.clear(); }

  // ---------------------------------------------------------------------------
  // EXECUTING phase
  // ---------------------------------------------------------------------------
  void runExecuting()
  {
    resetStability();
    geometry_msgs::msg::Pose stable_pose_base;
    bool pose_locked = false;

    while (true)
    {
      // --- Wait for a detection candidate ---
      rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg;
      {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        bool got = queue_cv_.wait_for(lock, std::chrono::seconds(3),
                                      [this]
                                      { return !candidate_queue_.empty() || shutdown_; });
        if (shutdown_)
          return;
        if (!got || candidate_queue_.empty())
        {
          RCLCPP_WARN(this->get_logger(), "EXECUTING: no candidates — returning to IDLE");
          return;
        }
        msg = candidate_queue_.front();
        // Drain stale candidates, keep latest
        while (!candidate_queue_.empty())
        {
          msg = candidate_queue_.front();
          candidate_queue_.pop();
        }
      }

      // --- Pick best candidate that passes approach angle check ---
      geometry_msgs::msg::Pose best_pose_cam;
      bool found_valid = false;
      for (const auto &candidate : msg->grasps)
      {
        // Transform to base_link to check approach angle
        geometry_msgs::msg::Pose pose_base;
        if (!transformToBase(candidate.pose, pose_base))
          continue;

        if (approachAngleDeg(pose_base.orientation) < MIN_APPROACH_ANGLE_DEG)
        {
          RCLCPP_DEBUG(this->get_logger(),
                       "Candidate rejected: approach angle %.1f° < %.1f°",
                       approachAngleDeg(pose_base.orientation),
                       MIN_APPROACH_ANGLE_DEG);
          continue;
        }
        best_pose_cam = candidate.pose;
        found_valid = true;
        break;
      }

      if (!found_valid)
      {
        RCLCPP_WARN(this->get_logger(), "No candidate passed approach angle check");
        resetStability();
        continue;
      }

      // Transform best candidate to base_link
      geometry_msgs::msg::Pose best_pose_base;
      if (!transformToBase(best_pose_cam, best_pose_base))
      {
        resetStability();
        continue;
      }

      // --- Check stability ---
      if (!pose_locked)
      {
        if (checkStability(best_pose_base, stable_pose_base))
        {
          RCLCPP_INFO(this->get_logger(), "Pose stable — locking target");
          pose_locked = true;
        }
        else
        {
          RCLCPP_DEBUG(this->get_logger(), "Pose not yet stable, stepping toward candidate");
        }
      }

      // --- Check depth threshold ---
      double object_depth;
      {
        std::lock_guard<std::mutex> lock(centroid_mutex_);
        if (!has_centroid_)
        {
          RCLCPP_WARN(this->get_logger(), "No centroid — cannot check depth");
          continue;
        }
        object_depth = latest_centroid_.point.z;
      }

      /*
      // --- Guard: too close without pose lock ---
      if (!pose_locked && object_depth < FINAL_EXEC_THRESH_M)
      {
        RCLCPP_WARN(this->get_logger(),
                    "Within %.3fm but pose not locked — stepping back",
                    FINAL_EXEC_THRESH_M);

        auto cur = mtc_planner_->getCurrentPose();
        geometry_msgs::msg::Pose retreat = cur.pose;
        retreat.position.z += APPROACH_STEP_M; // retreat upward in base_link

        mtc_planner_->moveCartesianStep(retreat);
        resetStability();
        continue;
      }
      */

      // --- Final execute: within threshold + pose locked ---
      if (pose_locked) //&& object_depth < FINAL_EXEC_THRESH_M) --- Old flag ---
      {
        RCLCPP_INFO(this->get_logger(),
                    "Depth %.3fm < %.3fm and pose stable — executing final Cartesian move",
                    object_depth, FINAL_EXEC_THRESH_M);
        if (mtc_planner_->moveCartesianStep(stable_pose_base))
        {
          RCLCPP_INFO(this->get_logger(), "Final Cartesian move succeeded");
          closeGripper();
        }
        else
        {
          RCLCPP_WARN(this->get_logger(), "Cartesian execute failed — stepping back up and forward");
          auto cur = mtc_planner_->getCurrentPose();
          geometry_msgs::msg::Pose fallback = cur.pose;
          fallback.position.z += APPROACH_STEP_M;
          fallback.position.x += APPROACH_STEP_M;
          mtc_planner_->moveCartesianStep(fallback);
          resetStability();
          pose_locked = false;
          continue;
        }
        return; // back to IDLE either way
      }

      continue;
      /*
      // --- Incremental step toward target ---
      auto current_pose_stamped = mtc_planner_->getCurrentPose();
      const auto &cur = current_pose_stamped.pose;

      // Use locked pose if available, otherwise current best
      const auto &target = pose_locked ? stable_pose_base : best_pose_base;

      // Translation: step APPROACH_STEP_M toward target
      double dx = target.position.x - cur.position.x;
      double dy = target.position.y - cur.position.y;
      double dz = target.position.z - cur.position.z;
      double dist = std::sqrt(dx * dx + dy * dy + dz * dz);

      geometry_msgs::msg::Pose step_pose;
      if (dist < APPROACH_STEP_M)
      {
        // Close enough — go directly (final step before threshold triggers)
        step_pose.position = target.position;
      }
      else
      {
        double scale = APPROACH_STEP_M / dist;
        step_pose.position.x = cur.position.x + dx * scale;
        step_pose.position.y = cur.position.y + dy * scale;
        step_pose.position.z = cur.position.z + dz * scale;
      }

      // Orientation: slerp toward target, capped at MAX_ORIENT_STEP_DEG
      double full_angle = angleBetweenQuats(cur.orientation, target.orientation);
      double t = (full_angle > 1e-3)
                     ? std::min(1.0, MAX_ORIENT_STEP_DEG / full_angle)
                     : 1.0;
      step_pose.orientation = slerpQuat(cur.orientation, target.orientation, t);

      if (!mtc_planner_->moveCartesianStep(step_pose))
      {
        RCLCPP_WARN(this->get_logger(), "Incremental step failed — resetting stability");
        resetStability();
        pose_locked = false;
      }
      */
    }
  }

  // ---------------------------------------------------------------------------
  // Just close gripper with approach handled by selecting loop
  // ---------------------------------------------------------------------------

  void runExecutingSimple()
  {
    RCLCPP_INFO(this->get_logger(), "Running simple execute — closing gripper");
    closeGripper();
  }
  // ---------------------------------------------------------------------------
  // Worker loop
  // ---------------------------------------------------------------------------
  void workerLoop()
  {
    std::this_thread::sleep_for(std::chrono::seconds(2));
    addSafetyWalls();
    while (!mtc_planner_->moveToHome())
    {
      RCLCPP_WARN(this->get_logger(), "Initial homing failed, retrying...");
      std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    publishState(State::IDLE);

    while (!debug_flag_)
    {
      // --- Wait for centroid (object detected) ---
      {
        std::unique_lock<std::mutex> lock(centroid_mutex_);
        queue_cv_.wait(lock, [this]
                       { return has_centroid_ || shutdown_; });
        if (shutdown_)
          return;
        has_centroid_ = false;
      }

      while (!mtc_planner_->moveToHome())
      {
        RCLCPP_WARN(this->get_logger(), "Initial homing failed, retrying...");
        std::this_thread::sleep_for(std::chrono::seconds(1));
      }

      // --- SELECTING phase ---
      publishState(State::SELECTING);

      int steps = 0;
      while (steps < MAX_APPROACH_STEPS)
      {
        double object_depth;
        {
          std::lock_guard<std::mutex> lock(centroid_mutex_);
          if (!has_centroid_)
          {
            RCLCPP_WARN(this->get_logger(), "Centroid lost — returning to IDLE");
            break;
          }
          object_depth = latest_centroid_.point.z;
        }

        if (object_depth < EXECUTE_DEPTH_THRESH_M)
        {
          RCLCPP_INFO(this->get_logger(),
                      "Object at %.3fm — entering EXECUTING", object_depth);
          publishState(State::EXECUTING);
          openGripper();
          if (USE_SIMPLE_EXECUTE)
            runExecutingSimple();
          else
            runExecuting();
          break;
        }

        if (!intrinsics_received_)
        {
          std::this_thread::sleep_for(std::chrono::milliseconds(100));
          continue;
        }

        auto current_pose_stamped = mtc_planner_->getCurrentPose();
        geometry_msgs::msg::PoseStamped current_pose_cam;
        try
        {
          tf_buffer_.transform(current_pose_stamped, current_pose_cam,
                               "camera_color_optical_frame",
                               tf2::durationFromSec(0.1));
        }
        catch (const tf2::TransformException &ex)
        {
          RCLCPP_WARN(this->get_logger(), "EEF transform failed: %s", ex.what());
          break;
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
          tf_buffer_.transform(goal_pose_cam, goal_pose_base, "base_link",
                               tf2::durationFromSec(0.1));
        }
        catch (const tf2::TransformException &ex)
        {
          RCLCPP_WARN(this->get_logger(), "Goal transform failed: %s", ex.what());
          break;
        }

        if (!mtc_planner_->moveCartesianStep(goal_pose_base.pose))
        {
          RCLCPP_WARN(this->get_logger(), "Cartesian step failed — returning to IDLE");
          break;
        }

        steps++;
      }

      RCLCPP_INFO(this->get_logger(), "Returning to IDLE");
      mtc_planner_->moveToHome();
      publishState(State::IDLE);
    }
  }

  // ---------------------------------------------------------------------------
  // Safety walls — added to planning scene at startup
  // ---------------------------------------------------------------------------
  void addSafetyWalls()
  {
    // Wait for move_group planning scene service to be ready
    std::this_thread::sleep_for(std::chrono::seconds(3));
    moveit::planning_interface::PlanningSceneInterface psi;

    // Wall definitions: id, cx, cy, cz, sx, sy, sz (all metres)
    struct Wall
    {
      std::string id;
      double cx, cy, cz, sx, sy, sz;
    };
    const double T = 0.03; // wall thickness
    const std::vector<Wall> walls = {
        // +X wall at x=0.15
        {"+x_wall", 0.15 + T / 2, 0.0, 0.5, T, 0.60 + T, 1.0},
        // +Y wall at y=0.30
        {"+y_wall", 0.0, 0.30 + T / 2, 0.5, 2.0, T, 1.0},
        // -Y wall at y=-0.30
        {"-y_wall", 0.0, -0.30 - T / 2, 0.5, 2.0, T, 1.0},
        // Table surface: 75x75cm, starts at x=-0.05, center at x=-0.425, z=0.21
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

    // Retry until move_group planning scene is ready
    // Note: applyCollisionObjects is non-blocking — poll until confirmed
    while (rclcpp::ok())
    {
      psi.applyCollisionObjects(objs);
      auto known = psi.getKnownObjectNames();
      bool all_added = true;
      for (const auto &w : walls)
      {
        if (std::find(known.begin(), known.end(), w.id) == known.end())
        {
          all_added = false;
          break;
        }
      }
      if (all_added)
      {
        RCLCPP_INFO(this->get_logger(), "Safety walls added to planning scene");
        break;
      }
      RCLCPP_WARN(this->get_logger(), "Waiting for planning scene to accept safety walls...");
      std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
  }

  // ---------------------------------------------------------------------------
  // Gripper helpers
  // ---------------------------------------------------------------------------
  bool openGripper()
  {
    rm_ros_interfaces::msg::Gripperset msg;
    msg.position = 1000;
    msg.block = false;
    gripper_position_pub_->publish(msg);
    std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    RCLCPP_INFO(this->get_logger(), "Gripper opened");
    return true;
  }

  bool closeGripper()
  {
    rm_ros_interfaces::msg::Gripperpick msg;
    msg.speed = 200;
    msg.force = 200;
    msg.block = false;
    gripper_pick_on_pub_->publish(msg);
    std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    RCLCPP_INFO(this->get_logger(), "Gripper closed");
    return true;
  }

  // ---------------------------------------------------------------------------
  // TF2 helper
  // ---------------------------------------------------------------------------
  bool transformToBase(const geometry_msgs::msg::Pose &pose_in,
                       geometry_msgs::msg::Pose &pose_out)
  {
    geometry_msgs::msg::PoseStamped stamped_in, stamped_out;
    stamped_in.header.frame_id = "camera_color_optical_frame";
    stamped_in.header.stamp = this->now();
    stamped_in.pose = pose_in;
    try
    {
      tf_buffer_.transform(stamped_in, stamped_out, "base_link",
                           tf2::durationFromSec(1.0));
      pose_out = stamped_out.pose;
      return true;
    }
    catch (const tf2::TransformException &ex)
    {
      RCLCPP_WARN(this->get_logger(), "TF2 failed: %s", ex.what());
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Members
  // ---------------------------------------------------------------------------
  double fx_ = 0.0, fy_ = 0.0, image_cx_ = 0.0, image_cy_ = 0.0;
  bool intrinsics_received_ = false;
  rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::SharedPtr camera_info_sub_;

  State state_;
  tf2_ros::Buffer tf_buffer_;
  tf2_ros::TransformListener tf_listener_;
  std::shared_ptr<MtcPlanner> mtc_planner_;

  geometry_msgs::msg::PointStamped latest_centroid_;
  bool has_centroid_ = false;
  std::mutex centroid_mutex_;

  rclcpp::Subscription<rm_ros_interfaces::msg::GraspCandidateArray>::SharedPtr grasp_sub_;
  rclcpp::Subscription<geometry_msgs::msg::PointStamped>::SharedPtr centroid_sub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperset>::SharedPtr gripper_position_pub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperpick>::SharedPtr gripper_pick_on_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pipeline_state_pub_;

  std::thread worker_thread_;
  std::queue<rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr> candidate_queue_;
  std::mutex queue_mutex_;
  std::condition_variable queue_cv_;
  bool shutdown_;
  bool debug_flag_ = false;
  bool grasped_ = false;

  // Stability window
  std::deque<geometry_msgs::msg::Pose> stability_window_;
};

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = GraspStateMachine::create();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}