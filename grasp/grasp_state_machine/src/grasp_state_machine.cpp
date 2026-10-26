#include <atomic>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <future>
#include <mutex>
#include <queue>
#include <thread>
#include <cmath>
#include <stdexcept>

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
#include <std_msgs/msg/empty.hpp>
#include <std_msgs/msg/string.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <rm_ros_interfaces/msg/gripperpick.hpp>
#include <rm_ros_interfaces/msg/gripperset.hpp>
#include <rm_ros_interfaces/msg/stop.hpp>
#include <grasp_interfaces/msg/grasp_candidate_array.hpp>
#include "grasp_state_machine/mtc_planner.hpp"

// Tuning values and topic names come from grasp/grasp_config.yaml (section grasp_state_machine)
// and shared/global_config.yaml, loaded as ROS parameters by grasp_state_machine.launch.py.
// See the members under "Tuning values" below.

// ===========================================================================
// State definitions
// ===========================================================================
enum class State
{
  IDLE,
  SELECTING,
  EXECUTING,
  STOPPED // an e-stop key was pressed: nothing is sent until R (T1.38)
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
  case State::STOPPED:
    return "STOPPED";
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
    node->mtc_planner_ = std::make_shared<MtcPlanner>(node, node->stopped_);
    node->worker_thread_ = std::thread(&GraspStateMachine::workerLoop, node.get());
    return node;
  }

  ~GraspStateMachine()
  {
    {
      // Both locks: the worker reads shutdown_ under centroid_mutex_ in IDLE and under
      // queue_mutex_ in EXECUTING. Setting it under only one could let the notify land between
      // the other wait's check and its sleep, and the worker would never wake (CODE_AUDIT C1)
      std::scoped_lock lock(queue_mutex_, centroid_mutex_);
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
    APPROACH_STEP_M = param("approach_step_m").as_double();
    APPROACH_STEP_FINAL = param("approach_step_final_m").as_double();
    MAX_APPROACH_STEPS = static_cast<int>(param("max_approach_steps").as_int());
    EXECUTE_DEPTH_THRESH_M = param("execute_depth_thresh_m").as_double();
    CENTROID_MAX_AGE_S = param("centroid_max_age_s").as_double();
    GRASP_REQUEST_TIMEOUT_S = param("grasp_request_timeout_s").as_double();
    TABLE_TOP_Z_M = param("table_top_z_m").as_double();
    FINAL_EXEC_THRESH_M = param("final_exec_thresh_m").as_double();
    CENTROID_TARGET_OFFSET_X = param("centroid_target_offset_x_px").as_double();
    CENTROID_TARGET_OFFSET_Y = param("centroid_target_offset_y_px").as_double();
    MIN_APPROACH_ANGLE_DEG = param("min_approach_angle_deg").as_double();
    MAX_ORIENT_STEP_DEG = param("max_orient_step_deg").as_double();
    USE_SIMPLE_EXECUTE = param("use_simple_execute").as_bool();
    USE_SLERP_EXECUTE = param("use_slerp_execute").as_bool();
    STABILITY_N_FRAMES = static_cast<int>(param("stability_n_frames").as_int());
    STABILITY_TRANS_MM = param("stability_trans_mm").as_double();
    STABILITY_ROT_DEG = param("stability_rot_deg").as_double();
    MAX_GRASP_ATTEMPTS = static_cast<int>(param("max_grasp_attempts").as_int());

    camera_info_sub_ = this->create_subscription<sensor_msgs::msg::CameraInfo>(
        topic("wrist_camera_info"), 1,
        std::bind(&GraspStateMachine::cameraInfoCallback, this, std::placeholders::_1));

    grasp_sub_ = this->create_subscription<grasp_interfaces::msg::GraspCandidateArray>(
        topic("grasp_candidates"), 10,
        std::bind(&GraspStateMachine::graspCallback, this, std::placeholders::_1));

    // The detector's measured box around the object, added to MoveIt's scene on lock (T1.48)
    target_sub_ = this->create_subscription<moveit_msgs::msg::CollisionObject>(
        topic("grasp_target_object"), 10,
        [this](const moveit_msgs::msg::CollisionObject::SharedPtr msg)
        {
          std::lock_guard<std::mutex> lock(target_mutex_);
          latest_target_ = msg;
        });

    centroid_sub_ = this->create_subscription<geometry_msgs::msg::PointStamped>(
        topic("object_centroid_2d"), 10,
        std::bind(&GraspStateMachine::centroidCallback, this, std::placeholders::_1));

    grasp_request_sub_ = this->create_subscription<std_msgs::msg::Empty>(
        topic("manipulator_grasp_request"), 10,
        std::bind(&GraspStateMachine::graspRequestCallback, this, std::placeholders::_1));

    release_sub_ = this->create_subscription<std_msgs::msg::Bool>(
        topic("manipulator_release"), 10,
        std::bind(&GraspStateMachine::releaseCallback, this, std::placeholders::_1));

    // The e-stop pane's keys (arm/estop/estop.py) reach this node as well as the driver (T1.38).
    // E and S stop it, R resumes it. E and R share one topic: state true is E, false is R
    estop_sub_ = this->create_subscription<rm_ros_interfaces::msg::Stop>(
        topic("rm_driver_emergency_stop_cmd"), 10,
        [this](const rm_ros_interfaces::msg::Stop::SharedPtr msg)
        { msg->state ? stop("emergency stop, E") : resume(); });

    move_stop_sub_ = this->create_subscription<std_msgs::msg::Empty>(
        topic("rm_driver_move_stop_cmd"), 10,
        [this](const std_msgs::msg::Empty::SharedPtr) { stop("soft stop, S"); });

    gripper_position_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperset>(
        topic("rm_driver_set_gripper_position_cmd"), 10);

    gripper_pick_on_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperpick>(
        topic("rm_driver_set_gripper_pick_on_cmd"), 10);

    pipeline_state_pub_ = this->create_publisher<std_msgs::msg::String>(
        topic("pipeline_state"), 10);

    return_to_user_pub_ = this->create_publisher<std_msgs::msg::Bool>(topic("manipulator_return_to_user"), 10);

    manipulation_done_pub_ = this->create_publisher<std_msgs::msg::Empty>(topic("manipulation_done"), 10);

    RCLCPP_INFO(this->get_logger(), "Grasp state machine constructed");
  }

  // A parameter from the config files. There is no fallback value: a missing one stops the node
  // at start-up rather than letting the arm run on a guessed value.
  rclcpp::Parameter param(const std::string &name)
  {
    if (!this->has_parameter(name))
      throw std::runtime_error("missing parameter '" + name + "'. Start the node with "
                               "grasp_state_machine.launch.py, which loads shared/global_config.yaml "
                               "and grasp/grasp_config.yaml");
    return this->get_parameter(name);
  }

  // A topic name from the config files: key "x" is parameter "topics.x".
  std::string topic(const std::string &key) { return param("topics." + key).as_string(); }

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

  void graspCallback(const grasp_interfaces::msg::GraspCandidateArray::SharedPtr msg)
  {
    if (state_ != State::EXECUTING || msg->grasps.empty())
      return;
    {
      std::lock_guard<std::mutex> lock(queue_mutex_);
      candidate_queue_.push(msg);
    }
    queue_cv_.notify_one();
  }

  // Centroids count only from a grasp request until EXECUTING takes its snapshot (T1.25).
  // Segmentation publishes on every frame, so without the gate any centroid would start the arm.
  void centroidCallback(const geometry_msgs::msg::PointStamped::SharedPtr msg)
  {
    std::lock_guard<std::mutex> lock(centroid_mutex_);
    if (!accepting_centroids_)
    {
      RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                           "Centroid ignored: no grasp request open");
      return;
    }
    latest_centroid_ = *msg;
    has_centroid_ = true;
    queue_cv_.notify_one();
  }

  // Opens the gate, only while the worker waits in IDLE. waiting_in_idle_ changes under the same
  // lock, so a request is either taken before the worker leaves IDLE or refused after.
  void graspRequestCallback(const std_msgs::msg::Empty::SharedPtr)
  {
    std::lock_guard<std::mutex> lock(centroid_mutex_);
    if (stopped_)
    {
      RCLCPP_WARN(this->get_logger(), "Grasp request ignored: stopped. Press R in the e-stop pane first");
      return;
    }
    if (!waiting_in_idle_)
    {
      RCLCPP_WARN(this->get_logger(), "Grasp request ignored: busy, not waiting in IDLE");
      return;
    }
    accepting_centroids_ = true;
    has_centroid_ = false;
    request_deadline_ = std::chrono::steady_clock::now() +
                        std::chrono::duration_cast<std::chrono::steady_clock::duration>(
                            std::chrono::duration<double>(GRASP_REQUEST_TIMEOUT_S));
    RCLCPP_INFO(this->get_logger(), "Grasp request: accepting centroids for %.1fs",
                GRASP_REQUEST_TIMEOUT_S);
    queue_cv_.notify_one();
  }

  // Lets go of the held object (T1.14). Accepted from the gripper closing until the gripper opens,
  // so a release said during the move to the return pose is kept and acted on there.
  void releaseCallback(const std_msgs::msg::Bool::SharedPtr msg)
  {
    if (!msg->data)
      return;
    std::lock_guard<std::mutex> lock(centroid_mutex_);
    if (!accepting_release_)
    {
      RCLCPP_WARN(this->get_logger(), "Release ignored: not holding an object");
      return;
    }
    release_received_ = true;
    RCLCPP_INFO(this->get_logger(), "Release received");
    queue_cv_.notify_one();
  }

  // Runs on the spin thread, so it acts while the worker is blocked inside a move. It cancels that
  // move and wakes every wait. The worker then unwinds, sending nothing more, and waits for R in
  // waitForResume. The gripper is left as it is, so a held object is not dropped (T1.38)
  void stop(const char *why)
  {
    {
      std::scoped_lock lock(queue_mutex_, centroid_mutex_); // both waits, as in the destructor
      stopped_ = true;
    }
    queue_cv_.notify_all();
    mtc_planner_->stopMotion();
    RCLCPP_WARN(this->get_logger(), "STOP (%s): move cancelled, nothing more is sent until R", why);
  }

  void resume()
  {
    {
      std::scoped_lock lock(queue_mutex_, centroid_mutex_);
      if (!stopped_)
        return;
      stopped_ = false;
    }
    queue_cv_.notify_all();
    RCLCPP_INFO(this->get_logger(), "Resume (R) received");
  }

  // After a stop: say so, move nothing, wait for R, then IDLE. The stopped request is dropped.
  // The next grasp request homes the arm first, as every request does
  void waitForResume()
  {
    publishState(State::STOPPED);
    {
      std::unique_lock<std::mutex> lock(centroid_mutex_);
      accepting_release_ = false; // a release opens the gripper, and that waits for a new grasp
      release_received_ = false;
      queue_cv_.wait(lock, [this] { return !stopped_ || shutdown_; });
    }
    if (!shutdown_)
      publishState(State::IDLE);
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
    if (gripperRefused("open"))
      return;
    rm_ros_interfaces::msg::Gripperset msg;
    msg.position = 1000;
    msg.block = false;
    gripper_position_pub_->publish(msg);
    std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    RCLCPP_INFO(this->get_logger(), "Gripper opened");
  }

  // No gripper command after a stop: the gripper stays as it was (T1.38)
  bool gripperRefused(const char *what)
  {
    if (!stopped_)
      return false;
    RCLCPP_WARN(this->get_logger(), "Gripper %s not sent: stopped", what);
    return true;
  }

  void closeGripper()
  {
    if (gripperRefused("close"))
      return;
    rm_ros_interfaces::msg::Gripperpick msg;
    msg.speed = 200;
    msg.force = 150;
    msg.block = false;
    gripper_pick_on_pub_->publish(msg);
    {
      // Closing means holding, so a release counts from here (T1.14)
      std::lock_guard<std::mutex> lock(centroid_mutex_);
      accepting_release_ = true;
    }
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
        {"table", -0.425, 0.0, TABLE_TOP_Z_M - T / 2, 0.75, 0.75, T},
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
      if (shutdown_ || stopped_)
        return;
      RCLCPP_WARN(this->get_logger(), "Homing failed, retrying...");
      std::this_thread::sleep_for(std::chrono::seconds(1));
    }
  }

  void returnWithRetry()
  {
    while (!mtc_planner_->moveToReturn())
    {
      if (shutdown_ || stopped_)
        return;
      RCLCPP_WARN(this->get_logger(), "Return failed, retrying...");
      std::this_thread::sleep_for(std::chrono::seconds(1));
    }
  }

  // After a grasp: hold the object out at the return pose until /manipulator/release, then let go
  // (T1.14). There is no timeout, so the arm never drops the object on its own. Grasp requests are
  // refused as busy meanwhile, because the worker is not waiting in IDLE.
  void holdUntilRelease()
  {
    returnWithRetry();
    if (stopped_)
      return;
    std_msgs::msg::Bool return_msg;
    return_msg.data = true;
    return_to_user_pub_->publish(return_msg);
    // Done before release: nav reads it as "holding the object" (CHANNEL_CONTRACT A-1, B-5)
    manipulation_done_pub_->publish(std_msgs::msg::Empty());
    RCLCPP_INFO(this->get_logger(), "Holding the object: waiting for /manipulator/release");
    {
      std::unique_lock<std::mutex> lock(centroid_mutex_);
      queue_cv_.wait(lock, [this] { return release_received_ || shutdown_ || stopped_; });
      accepting_release_ = false;
      release_received_ = false;
    }
    if (shutdown_ || stopped_)
      return;
    openGripper();
    mtc_planner_->removeTarget();
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
    grasp_interfaces::msg::GraspCandidateArray::SharedPtr msg;
    {
      std::unique_lock<std::mutex> lock(queue_mutex_);
      bool got = queue_cv_.wait_for(lock, std::chrono::seconds(3),
                                    [this]
                                    { return !candidate_queue_.empty() || shutdown_ || stopped_; });
      if (shutdown_ || stopped_)
        return true;
      if (!got || candidate_queue_.empty())
      {
        RCLCPP_WARN(this->get_logger(), "EXECUTING: no candidates in 3 s, back to IDLE. The AnyGrasp node log says why (T1.37)");
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
      // A grasp that already failed to plan fails again: take the next one (T1.48). It used to
      // retry the same grasp forever (2026-10-26)
      if (std::any_of(failed_poses_.begin(), failed_poses_.end(), [&](const geometry_msgs::msg::Pose &f)
                      { return transDist(f.position, pose_base.position) <= STABILITY_TRANS_MM &&
                               angleBetweenQuats(f.orientation, pose_base.orientation) <= STABILITY_ROT_DEG; }))
        continue;
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

      // MoveIt must know where the object is, or its path goes through it (CODE_AUDIT A4)
      moveit_msgs::msg::CollisionObject::SharedPtr target;
      {
        std::lock_guard<std::mutex> lock(target_mutex_);
        target = latest_target_;
      }
      if (!target || !mtc_planner_->addTarget(*target))
      {
        RCLCPP_WARN(this->get_logger(), "EXECUTING: no target box in the planning scene, not moving. "
                                        "The AnyGrasp node log says why (T1.48)");
        resetStability();
        pose_locked = false;
        return false;
      }

      RCLCPP_INFO(this->get_logger(),
                  "EXECUTING: pose locked, depth=%.3fm — approaching the grasp%s",
                  object_depth, USE_SLERP_EXECUTE ? " (slerp)" : "");
      bool moved = mtc_planner_->approachGrasp(exec_pose);
      if (stopped_)
        return true; // the stop cancelled or refused the move: no retry
      if (moved)
      {
        RCLCPP_INFO(this->get_logger(), "EXECUTING: approach succeeded");
        closeGripper();
        // So the move to the return pose plans with the object in hand
        if (!stopped_ && !mtc_planner_->attachTarget())
          RCLCPP_WARN(this->get_logger(), "EXECUTING: could not attach the target in the planning scene");
        grasped_ = true;
        return true; // done
      }
      // Planning failed, so the arm has not moved: no retreat needed
      failed_poses_.push_back(stable_pose_base);
      if (static_cast<int>(failed_poses_.size()) >= MAX_GRASP_ATTEMPTS)
      {
        RCLCPP_WARN(this->get_logger(), "EXECUTING: %d grasps failed to plan, back to IDLE", MAX_GRASP_ATTEMPTS);
        return true;
      }
      RCLCPP_WARN(this->get_logger(), "EXECUTING: approach failed, trying the next grasp (%zu of %d failed)",
                  failed_poses_.size(), MAX_GRASP_ATTEMPTS);
      resetStability();
      pose_locked = false;
      return false; // next candidate
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
      if (stopped_)
        waitForResume();
      if (shutdown_)
        return;
      // =====================================================================
      // IDLE — wait for object detection
      // =====================================================================
      // Waits for a grasp request, then for a centroid. queue_cv_ is shared with EXECUTING's wait
      // on queue_mutex_. That is allowed because only this worker thread ever waits on it, so the
      // two waits never overlap (CODE_AUDIT C1). Each notifier changes its flag under the mutex
      // of the wait it wakes.
      {
        std::unique_lock<std::mutex> lock(centroid_mutex_);
        // Close the gate on every entry, so each request gives one attempt. Reset under the lock,
        // because the callbacks set these from the spin thread (race, audit C3)
        accepting_centroids_ = false;
        has_centroid_ = false;
        waiting_in_idle_ = true;
        while (!shutdown_ && !stopped_ && !(accepting_centroids_ && has_centroid_))
        {
          if (!accepting_centroids_)
          {
            queue_cv_.wait(lock);
            continue;
          }
          queue_cv_.wait_until(lock, request_deadline_);
          // Re-read after waking: a second request moves the deadline, a centroid ends the wait
          if (accepting_centroids_ && !has_centroid_ &&
              std::chrono::steady_clock::now() >= request_deadline_)
          {
            accepting_centroids_ = false;
            RCLCPP_WARN(this->get_logger(), "Grasp request lapsed: no centroid within %.1fs",
                        GRASP_REQUEST_TIMEOUT_S);
          }
        }
        // Leaving IDLE in the same locked block that saw the centroid: a request arriving from
        // here on is refused, and the deadline is never read again this cycle
        waiting_in_idle_ = false;
        if (shutdown_)
          return;
        if (stopped_)
          continue;
      }

      // A target left by the last cycle (failed, stopped, or this node restarted: move_group keeps
      // the scene) would block the arm around where the object used to be (T1.48)
      mtc_planner_->removeTarget();
      // Re-home beore each approach cycle
      homeWithRetry();
      if (stopped_)
        continue;
      // =====================================================================
      // SELECTING — approach object using 2D centroid
      // =====================================================================
      publishState(State::SELECTING);

      bool transition_to_executing = false;
      for (int steps = 0; steps < MAX_APPROACH_STEPS && !stopped_; ++steps)
      {
        double object_depth;
        double age_s;
        {
          std::lock_guard<std::mutex> lock(centroid_mutex_);
          age_s = (this->now() - rclcpp::Time(latest_centroid_.header.stamp)).seconds();
          object_depth = latest_centroid_.point.z;
        }
        // The stamp is the camera frame's, so the age includes segmentation time
        if (age_s > CENTROID_MAX_AGE_S)
        {
          RCLCPP_WARN(this->get_logger(),
                      "SELECTING: centroid %.2fs old (limit %.2fs), object lost — returning to IDLE",
                      age_s, CENTROID_MAX_AGE_S);
          break;
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

      if (stopped_)
        continue;
      if (!transition_to_executing)
      {
        publishState(State::IDLE);
        continue;
      }
      // ==================================================================
      // EXECUTING
      // ==================================================================
      publishState(State::EXECUTING);
      {
        std::lock_guard<std::mutex> lock(centroid_mutex_);
        centroid_snapshot_ = latest_centroid_;
        accepting_centroids_ = false; // the snapshot is the target from here on (T1.25)
      }
      {
        // Candidates from an earlier cycle's hold were seen from the return pose, not from here
        std::lock_guard<std::mutex> lock(queue_mutex_);
        candidate_queue_ = {};
      }
      openGripper();
      grasped_ = false;

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

        // The gripper is open here, so going home from a failed step is safe
        bool moved = mtc_planner_->moveCartesianStep(goal_pose_base.pose);
        if (!moved && !stopped_)
        {
          RCLCPP_WARN(this->get_logger(), "EXECUTING: final Cartesian step failed — back to HOME and IDLE");
        }
        else if (moved && !stopped_)
        {
          executingSimple();
          grasped_ = true;
          // Logged without checking the jaws: judge a grasp by eye (GRASP_BRINGUP_STEPS)
          RCLCPP_INFO(this->get_logger(), "Object grasped successfully");
        }
      }
      else
      {
        bool pose_locked = false;
        geometry_msgs::msg::Pose stable_pose_base;
        resetStability();
        failed_poses_.clear();

        bool executing_done = false;
        while (!executing_done && !stopped_)
          executing_done = executingStep(pose_locked, stable_pose_base);
      }
      if (grasped_ && !stopped_)
        holdUntilRelease();
      if (shutdown_)
        return;
      if (stopped_)
        continue;
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
  rclcpp::Subscription<grasp_interfaces::msg::GraspCandidateArray>::SharedPtr grasp_sub_;
  rclcpp::Subscription<geometry_msgs::msg::PointStamped>::SharedPtr centroid_sub_;
  rclcpp::Subscription<moveit_msgs::msg::CollisionObject>::SharedPtr target_sub_;
  rclcpp::Subscription<std_msgs::msg::Empty>::SharedPtr grasp_request_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr release_sub_;
  rclcpp::Subscription<rm_ros_interfaces::msg::Stop>::SharedPtr estop_sub_;
  rclcpp::Subscription<std_msgs::msg::Empty>::SharedPtr move_stop_sub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperset>::SharedPtr gripper_position_pub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperpick>::SharedPtr gripper_pick_on_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pipeline_state_pub_;
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr return_to_user_pub_;
  rclcpp::Publisher<std_msgs::msg::Empty>::SharedPtr manipulation_done_pub_;

  // TF2
  tf2_ros::Buffer tf_buffer_;
  tf2_ros::TransformListener tf_listener_;

  // Camera intrinsics
  double fx_ = 0.0, fy_ = 0.0, image_cx_ = 0.0, image_cy_ = 0.0;
  bool intrinsics_received_ = false;

  // State. Atomic: the worker writes it and graspCallback reads it on the spin thread (CODE_AUDIT C4)
  std::atomic<State> state_;

  // Motion planner
  std::shared_ptr<MtcPlanner> mtc_planner_;

  // Centroid (shared with callbacks)
  geometry_msgs::msg::PointStamped latest_centroid_;
  bool has_centroid_ = false;
  // The trigger gate (T1.25), also under centroid_mutex_
  bool accepting_centroids_ = false;
  bool waiting_in_idle_ = false;
  std::chrono::steady_clock::time_point request_deadline_;
  // The release gate (T1.14), also under centroid_mutex_
  bool accepting_release_ = false;
  bool release_received_ = false;
  std::mutex centroid_mutex_;
  geometry_msgs::msg::PointStamped centroid_snapshot_;

  // Grasp candidate queue (shared with callbacks)
  std::queue<grasp_interfaces::msg::GraspCandidateArray::SharedPtr> candidate_queue_;
  std::mutex queue_mutex_;
  std::condition_variable queue_cv_;

  // Worker thread
  std::thread worker_thread_;
  bool shutdown_;
  // Set by E or S, cleared by R (T1.38). Written under both mutexes, so a wait cannot miss it,
  // and atomic, because the worker and the planner also read it outside them
  std::atomic<bool> stopped_{false};

  // Stability window
  std::deque<geometry_msgs::msg::Pose> stability_window_;
  // Grasps that failed to plan this cycle, skipped from then on (worker thread only, T1.48)
  std::vector<geometry_msgs::msg::Pose> failed_poses_;

  // The newest target box from the detector (T1.48)
  moveit_msgs::msg::CollisionObject::SharedPtr latest_target_;
  std::mutex target_mutex_;

  // Flags
  bool debug_flag_ = false;
  bool grasped_ = false; // this cycle closed the gripper on the object (worker thread only)

  // Tuning values, set once in the constructor from grasp/grasp_config.yaml before the worker
  // thread starts. Names kept from when these were constants.
  double APPROACH_STEP_M;
  double APPROACH_STEP_FINAL;
  int MAX_APPROACH_STEPS;
  double EXECUTE_DEPTH_THRESH_M;
  double CENTROID_MAX_AGE_S;
  double GRASP_REQUEST_TIMEOUT_S;
  double TABLE_TOP_Z_M;
  double FINAL_EXEC_THRESH_M;
  double CENTROID_TARGET_OFFSET_X;
  double CENTROID_TARGET_OFFSET_Y;
  double MIN_APPROACH_ANGLE_DEG;
  double MAX_ORIENT_STEP_DEG;
  bool USE_SIMPLE_EXECUTE;
  bool USE_SLERP_EXECUTE;
  // Stability criterion
  int STABILITY_N_FRAMES;
  double STABILITY_TRANS_MM;
  double STABILITY_ROT_DEG;
  int MAX_GRASP_ATTEMPTS; // grasps tried per cycle before giving up (T1.48)
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