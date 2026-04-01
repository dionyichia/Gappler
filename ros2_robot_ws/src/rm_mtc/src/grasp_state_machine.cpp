#include <chrono>
#include <condition_variable>
#include <future>
#include <mutex>
#include <queue>
#include <thread>

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
static constexpr double APPROACH_STEP_M = 0.03;       // forward step size (metres)
static constexpr int MAX_APPROACH_STEPS = 30;         // abort threshold
static constexpr double EXECUTE_DEPTH_THRESH_M = 0.2; // transition to EXECUTING (metres)
static constexpr double CENTROID_GAIN = 0.001;        // pixels → metres lateral correction
static constexpr double IMAGE_CX = 657.9279;
static constexpr double IMAGE_CY = 375.1953;

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
    // Subscribers

    grasp_sub_ = this->create_subscription<rm_ros_interfaces::msg::GraspCandidateArray>(
        "/grasp_candidates", 10,
        std::bind(&GraspStateMachine::graspCallback, this, std::placeholders::_1));

    centroid_sub_ = this->create_subscription<geometry_msgs::msg::PointStamped>(
        "/object_centroid", 10,
        std::bind(&GraspStateMachine::centroidCallback, this, std::placeholders::_1));

    // Publishers
    gripper_position_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperset>(
        "/rm_driver/set_gripper_position_cmd", 10);

    gripper_pick_on_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperpick>(
        "/rm_driver/set_gripper_pick_on_cmd", 10);

    pipeline_state_pub_ = this->create_publisher<std_msgs::msg::String>(
        "/pipeline_state", 10);

    RCLCPP_INFO(this->get_logger(), "Grasp state machine ready. State: IDLE");
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
  // Callbacks — spin thread only, never block
  // ---------------------------------------------------------------------------
  void graspCallback(const rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg)
  {
    if (state_ != State::SELECTING)
    {
      RCLCPP_DEBUG(this->get_logger(), "Busy, ignoring new candidates");
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
  // Worker loop — all blocking work here
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

      // Wait for first candidates from AnyGrasp (now unblocked by SELECTING state)
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
          if (has_centroid_)
          {
            has_centroid_ = false;
            RCLCPP_WARN(this->get_logger(), "No candidates yet but centroid available — retrying SELECTING");
            continue;
          }
          RCLCPP_WARN(this->get_logger(), "No candidates and no centroid — returning to IDLE");
          mtc_planner_->moveToHome();
          publishState(State::IDLE);
          continue;
        }
        msg = candidate_queue_.front();
        candidate_queue_.pop();
      }

      // bool transitioned = false;
      int steps = 0;

      while (steps < MAX_APPROACH_STEPS)
      {
        // Get best candidate depth in camera frame
        float best_z = msg->grasps[0].pose.position.z;

        if (best_z < EXECUTE_DEPTH_THRESH_M)
        // {
        //   RCLCPP_INFO(this->get_logger(),
        //               "Object at %.3fm — transitioning to EXECUTING", best_z);
        //   transitioned = true;
        //   break;
        // }
        {
          // Transition to executing
          RCLCPP_INFO(this->get_logger(),
                      "Object at %.3fm — transitioning to EXECUTING", best_z);

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

        // 1. Get current EEF pose in base_link
        auto current_pose_stamped = mtc_planner_->getCurrentPose();

        // 2. Transform to camera_color_optical_frame
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

        // 3. Compute step vector toward centroid in camera frame, scaled to APPROACH_STEP_M
        geometry_msgs::msg::PoseStamped goal_pose_cam = current_pose_cam;
        {
          std::lock_guard<std::mutex> lock(centroid_mutex_);
          if (has_centroid_)
          {
            double dx = latest_centroid_.point.x - current_pose_cam.pose.position.x;
            double dy = latest_centroid_.point.y - current_pose_cam.pose.position.y;
            double dz = latest_centroid_.point.z - current_pose_cam.pose.position.z;
            double dist = std::sqrt(dx * dx + dy * dy + dz * dz);
            if (dist > 0)
            {
              double scale = APPROACH_STEP_M / dist;
              goal_pose_cam.pose.position.x += dx * scale;
              goal_pose_cam.pose.position.y += dy * scale;
              goal_pose_cam.pose.position.z += dz * scale;
            }
          }
          else
          {
            // If no centroid, return to IDLE state
            RCLCPP_WARN(this->get_logger(), "No centroid available — object lost, aborting SELECTING");
            has_centroid_ = false;
            mtc_planner_->moveToHome();
            break;
          }
        }

        // 4. Transform goal pose back to base_link
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

        // 5. Execute step
        if (!mtc_planner_->moveCartesianStep(goal_pose_base.pose))
        {
          RCLCPP_WARN(this->get_logger(), "Cartesian step failed — aborting SELECTING");
          break;
        }

        // Check for updated candidates (tracking still valid)
        {
          std::lock_guard<std::mutex> lock(queue_mutex_);
          if (!candidate_queue_.empty())
          {
            msg = candidate_queue_.back();
            // Drain stale candidates
            while (!candidate_queue_.empty())
              candidate_queue_.pop();
          }
        }

        if (msg->grasps.empty())
        {
          RCLCPP_WARN(this->get_logger(), "Tracking lost during SELECTING — returning to IDLE");
          mtc_planner_->moveToHome();
          break;
        }

        steps++;
      }

      // All paths return to IDLE in debug phase
      RCLCPP_INFO(this->get_logger(), "SELECTING complete — returning to IDLE");
      mtc_planner_->moveToHome();
      publishState(State::IDLE);

      //       if (!transitioned)
      // {
      //   RCLCPP_ERROR(this->get_logger(), "SELECTING failed — returning to IDLE");
      //   mtc_planner_->moveToHome();
      //   publishState(State::IDLE);
      //   continue;
      // }

      // // ---- EXECUTING phase ----
      // publishState(State::EXECUTING);

      // bool grasped = false;
      // for (const auto &candidate : msg->grasps)
      // {
      //   RCLCPP_INFO(this->get_logger(), "Trying candidate score: %.4f", candidate.score);

      //   geometry_msgs::msg::Pose pose_base;
      //   if (!transformToBase(candidate.pose, pose_base))
      //   {
      //     RCLCPP_WARN(this->get_logger(), "Transform failed, skipping");
      //     continue;
      //   }

      //   if (!openGripper())
      //   {
      //     RCLCPP_WARN(this->get_logger(), "Gripper open failed, trying next candidate");
      //     continue;
      //   }

      //   if (!mtc_planner_->moveToPose(pose_base))
      //   {
      //     RCLCPP_WARN(this->get_logger(), "moveToPose failed, trying next candidate");
      //     continue;
      //   }

      //   if (!closeGripper())
      //   {
      //     RCLCPP_WARN(this->get_logger(), "Gripper close failed, trying next candidate");
      //     continue;
      //   }

      //   if (!mtc_planner_->moveToHome())
      //   {
      //     RCLCPP_ERROR(this->get_logger(), "moveToHome failed but grasp succeeded — manual intervention may be required");
      //     grasped = true;
      //     break;
      //   }

      //   RCLCPP_INFO(this->get_logger(), "Grasp succeeded");
      //   grasped = true;
      //   break;
      // }

      // if (!grasped)
      // {
      //   RCLCPP_ERROR(this->get_logger(), "All candidates failed");
      //   mtc_planner_->moveToHome();
      //   publishState(State::IDLE);
      // }
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

  // ---- Replace closeGripper() ----
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
  // Members - essential variables outside of helper functions
  // ---------------------------------------------------------------------------
  State state_;
  tf2_ros::Buffer tf_buffer_;
  tf2_ros::TransformListener tf_listener_;
  std::shared_ptr<MtcPlanner> mtc_planner_;

  // Centroid
  geometry_msgs::msg::PointStamped latest_centroid_;
  bool has_centroid_ = false;
  std::mutex centroid_mutex_;

  // Subscriptions
  rclcpp::Subscription<rm_ros_interfaces::msg::GraspCandidateArray>::SharedPtr grasp_sub_;
  rclcpp::Subscription<geometry_msgs::msg::PointStamped>::SharedPtr centroid_sub_;

  // Publishers
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperset>::SharedPtr gripper_position_pub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperpick>::SharedPtr gripper_pick_on_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pipeline_state_pub_;

  // Worker thread
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