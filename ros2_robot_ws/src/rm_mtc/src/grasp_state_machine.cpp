#include <chrono>
#include <condition_variable>
#include <future>
#include <mutex>
#include <queue>
#include <thread>

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
static constexpr double APPROACH_STEP_M = 0.03;
static constexpr int MAX_APPROACH_STEPS = 30;
static constexpr double EXECUTE_DEPTH_THRESH_M = 0.20;
// Pixel offset below image centre to align object with gripper approach axis.
// Camera is offset 47.5mm from Link6 in Y — tune empirically from this starting point.
static constexpr double CENTROID_TARGET_OFFSET_X = 20.0; // Harcoded for current camera mounting, may need adjustment
static constexpr double CENTROID_TARGET_OFFSET_Y = 40.0; // Harcoded for current camera mounting, may need adjustment

// ---------------------------------------------------------------------------
// State definitions
// ---------------------------------------------------------------------------
enum class State
{
  IDLE,
  SELECTING,
  EXECUTING // unused in debug phase
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
  // CameraInfo callback — one-time latch
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
                "Intrinsics received: fx=%.2f fy=%.2f cx=%.2f cy=%.2f",
                fx_, fy_, image_cx_, image_cy_);
    camera_info_sub_.reset();
  }

  // ---------------------------------------------------------------------------
  // State publisher helper
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
    // Gate changed: was state_ == State::EXECUTING, now accept during SELECTING only
    if (state_ != State::SELECTING)
    {
      RCLCPP_DEBUG(this->get_logger(), "Not SELECTING, ignoring candidates");
      return;
    }
    if (msg->grasps.empty())
    {
      RCLCPP_WARN(this->get_logger(), "Received empty grasp candidates");
      return;
    }
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
  // Worker loop
  // ---------------------------------------------------------------------------
  void workerLoop()
  {
    std::this_thread::sleep_for(std::chrono::seconds(2));
    mtc_planner_->moveToHome();
    publishState(State::IDLE);

    while (true)
    {
      // ---- Wait for centroid (object detected) ----
      {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        queue_cv_.wait(lock, [this]
                       { return has_centroid_ || shutdown_; });
        if (shutdown_)
          return;
        has_centroid_ = false;
      }

      // ---- SELECTING phase ----
      publishState(State::SELECTING);

      rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg;
      {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        bool got_candidates = queue_cv_.wait_for(lock, std::chrono::seconds(5),
                                                 [this]
                                                 { return !candidate_queue_.empty() || shutdown_; });
        if (shutdown_)
          return;
        if (!got_candidates || candidate_queue_.empty())
        {
          RCLCPP_WARN(this->get_logger(), "No candidates received — returning to IDLE");
          mtc_planner_->moveToHome();
          publishState(State::IDLE);
          continue;
        }
        msg = candidate_queue_.front();
        candidate_queue_.pop();
      }

      int steps = 0;
      while (steps < MAX_APPROACH_STEPS)
      {
        // Use depth from SAM3 centroid (metres) as threshold
        double object_depth;
        {
          std::lock_guard<std::mutex> lock(centroid_mutex_);
          if (!has_centroid_)
          {
            RCLCPP_WARN(this->get_logger(), "No centroid available — object lost, aborting SELECTING");
            break;
          }
          object_depth = latest_centroid_.point.z;
        }

        if (object_depth < EXECUTE_DEPTH_THRESH_M)
        {
          RCLCPP_INFO(this->get_logger(),
                      "Object at %.3fm — transitioning to EXECUTING", object_depth);

          publishState(State::EXECUTING);

          bool grasped = false;
          for (const auto &candidate : msg->grasps)
          {
            geometry_msgs::msg::Pose pose_base;
            if (!transformToBase(candidate.pose, pose_base))
            {
              RCLCPP_WARN(this->get_logger(), "Transform failed, skipping candidate");
              continue;
            }

            if (!openGripper())
            {
              RCLCPP_WARN(this->get_logger(), "Gripper open failed, skipping candidate");
              continue;
            }

            if (!mtc_planner_->moveCartesianStep(pose_base))
            {
              RCLCPP_WARN(this->get_logger(), "Cartesian move to grasp pose failed, skipping candidate");
              continue;
            }

            if (!closeGripper())
            {
              RCLCPP_WARN(this->get_logger(), "Gripper close failed, skipping candidate");
              continue;
            }

            RCLCPP_INFO(this->get_logger(), "Grasp succeeded");
            grasped = true;
            break;
          }

          if (!grasped)
            RCLCPP_ERROR(this->get_logger(), "All candidates failed");

          break;
        }

        if (!intrinsics_received_)
        {
          RCLCPP_WARN(this->get_logger(), "Intrinsics not yet received, waiting...");
          std::this_thread::sleep_for(std::chrono::milliseconds(100));
          continue;
        }

        // Get current EEF pose in base_link
        auto current_pose_stamped = mtc_planner_->getCurrentPose();

        // Transform to camera frame
        geometry_msgs::msg::PoseStamped current_pose_cam;
        try
        {
          tf_buffer_.transform(current_pose_stamped, current_pose_cam,
                               "camera_color_optical_frame", tf2::durationFromSec(0.1));
        }
        catch (const tf2::TransformException &ex)
        {
          RCLCPP_WARN(this->get_logger(), "EEF transform failed: %s", ex.what());
          break;
        }

        // Compute combined lateral + forward step in camera frame
        geometry_msgs::msg::PoseStamped goal_pose_cam = current_pose_cam;
        {
          std::lock_guard<std::mutex> lock(centroid_mutex_);

          // Pixel error from gripper-aligned target (slightly below image centre)
          double px_err_x = latest_centroid_.point.x - (image_cx_ + CENTROID_TARGET_OFFSET_X);
          double px_err_y = latest_centroid_.point.y - (image_cy_ + CENTROID_TARGET_OFFSET_Y);
          double depth = latest_centroid_.point.z;

          // Convert pixel error to metres using pinhole model
          double lateral_x = (px_err_x / fx_) * depth;
          double lateral_y = (px_err_y / fy_) * depth;

          // Combined step vector: lateral correction + fixed forward step along camera Z
          double dx = lateral_x;
          double dy = lateral_y;
          double dz = APPROACH_STEP_M;

          // Normalise to APPROACH_STEP_M magnitude
          double magnitude = std::sqrt(dx * dx + dy * dy + dz * dz);
          double scale = APPROACH_STEP_M / magnitude;

          goal_pose_cam.pose.position.x += dx * scale;
          goal_pose_cam.pose.position.y += dy * scale;
          goal_pose_cam.pose.position.z += dz * scale;
        }

        // Transform goal back to base_link
        geometry_msgs::msg::PoseStamped goal_pose_base;
        try
        {
          tf_buffer_.transform(goal_pose_cam, goal_pose_base, "base_link",
                               tf2::durationFromSec(0.1));
        }
        catch (const tf2::TransformException &ex)
        {
          RCLCPP_WARN(this->get_logger(), "Goal pose transform failed: %s", ex.what());
          break;
        }

        if (!mtc_planner_->moveCartesianStep(goal_pose_base.pose))
        {
          RCLCPP_WARN(this->get_logger(), "Cartesian step failed — aborting SELECTING");
          break;
        }

        // Drain stale candidates
        {
          std::lock_guard<std::mutex> lock(queue_mutex_);
          if (!candidate_queue_.empty())
          {
            msg = candidate_queue_.back();
            while (!candidate_queue_.empty())
              candidate_queue_.pop();
          }
        }

        if (msg->grasps.empty())
        {
          RCLCPP_WARN(this->get_logger(), "Tracking lost during SELECTING — returning to IDLE");
          break;
        }

        steps++;
      }

      // All paths return to IDLE in debug phase
      RCLCPP_INFO(this->get_logger(), "SELECTING complete — returning to IDLE");
      mtc_planner_->moveToHome();
      publishState(State::IDLE);

      // ---- EXECUTING phase — commented out for debug phase ----
      // publishState(State::EXECUTING);
      // ... grasp execution logic ...
    }
  }

  // ---------------------------------------------------------------------------
  // Gripper helpers — kept but unused in debug phase
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
  // TF2 helper — kept for future EXECUTING phase
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
      tf_buffer_.transform(stamped_in, stamped_out, "base_link", tf2::durationFromSec(1.0));
      pose_out = stamped_out.pose;
      return true;
    }
    catch (const tf2::TransformException &ex)
    {
      RCLCPP_WARN(this->get_logger(), "TF2 transform failed: %s", ex.what());
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Members
  // ---------------------------------------------------------------------------
  // Intrinsics
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