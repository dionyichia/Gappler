#include <chrono>
#include <condition_variable>
#include <future>
#include <mutex>
#include <queue>
#include <thread>

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <std_msgs/msg/bool.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <rm_ros_interfaces/msg/gripperpick.hpp>
#include <rm_ros_interfaces/msg/gripperset.hpp>
#include <rm_ros_interfaces/msg/grasp_candidate_array.hpp>
#include "rm_mtc/mtc_planner.hpp"

// ---------------------------------------------------------------------------
// State definitions
// ---------------------------------------------------------------------------
enum class State
{
  IDLE,
  SELECTING,
  EXECUTING
};

// GraspStatemMachine is a ROS2 node
// Subscribes to grasp candidates topic and publishes to Gripperpick topic
// As a node, it has the ability to create publishers, subscribers, timers

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
    grasp_sub_ = this->create_subscription<rm_ros_interfaces::msg::GraspCandidateArray>(
        "/grasp_candidates", 10,
        std::bind(&GraspStateMachine::graspCallback, this, std::placeholders::_1));

    gripper_position_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperset>(
        "/rm_driver/set_gripper_position_cmd", 10);
    gripper_pick_on_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperpick>(
        "/rm_driver/set_gripper_pick_on_cmd", 10);

    gripper_position_result_sub_ = this->create_subscription<std_msgs::msg::Bool>(
        "/rm_driver/set_gripper_position_result", 10,
        std::bind(&GraspStateMachine::gripperPositionResultCallback, this, std::placeholders::_1));
    gripper_pick_on_result_sub_ = this->create_subscription<std_msgs::msg::Bool>(
        "/rm_driver/set_gripper_pick_on_result", 10,
        std::bind(&GraspStateMachine::gripperPickOnResultCallback, this, std::placeholders::_1));

    RCLCPP_INFO(this->get_logger(), "Grasp state machine ready. State: IDLE");
  }

  // ---------------------------------------------------------------------------
  // Grasp callback — spin thread only, never blocks
  // ---------------------------------------------------------------------------
  void graspCallback(const rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg)
  {
    if (state_ != State::IDLE)
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

  // ---------------------------------------------------------------------------
  // Worker loop — runs on dedicated thread, does all blocking work
  // ---------------------------------------------------------------------------
  void workerLoop()
  {
    // Move to home position on startup
    mtc_planner_->moveToHome();

    while (true)
    {
      rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg;
      {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        queue_cv_.wait(lock, [this]
                       { return !candidate_queue_.empty() || shutdown_; });
        if (shutdown_)
          return;
        msg = candidate_queue_.front();
        candidate_queue_.pop();
      }

      RCLCPP_INFO(this->get_logger(), "IDLE → SELECTING (%zu candidates)", msg->grasps.size());
      state_ = State::SELECTING;

      for (const auto &candidate : msg->grasps)
      {
        RCLCPP_INFO(this->get_logger(), "Trying candidate with score: %.4f", candidate.score);

        geometry_msgs::msg::Pose pose_base;
        if (!transformToBase(candidate.pose, pose_base))
        {
          RCLCPP_WARN(this->get_logger(), "Transform failed, skipping candidate");
          continue;
        }

        state_ = State::EXECUTING;
        RCLCPP_INFO(this->get_logger(), "SELECTING → EXECUTING");

        openGripper();

        if (!mtc_planner_->moveToPose(pose_base))
        {
          RCLCPP_WARN(this->get_logger(), "moveToPose failed, trying next candidate");
          state_ = State::SELECTING;
          continue;
        }

        closeGripper();

        if (!mtc_planner_->moveToHome())
        {
          RCLCPP_ERROR(this->get_logger(), "moveToHome failed. EXECUTING → IDLE");
          state_ = State::IDLE;
          return;
        }

        // Move back to home when in IDLE state
        RCLCPP_INFO(this->get_logger(), "Grasp succeeded. EXECUTING → IDLE");
        mtc_planner_->moveToHome();
        state_ = State::IDLE;
        return;
      }

      // Move back to home when in IDLE state
      RCLCPP_ERROR(this->get_logger(), "All candidates failed. SELECTING → IDLE");
      mtc_planner_->moveToHome();
      state_ = State::IDLE;
    }
  }

  // ---------------------------------------------------------------------------
  // Gripper helpers — called from worker thread, block on future
  // ---------------------------------------------------------------------------
  void openGripper()
  {
    gripper_position_promise_ = std::make_shared<std::promise<bool>>();
    auto future = gripper_position_promise_->get_future();
    rm_ros_interfaces::msg::Gripperset msg;
    msg.position = 1000;
    msg.block = true;
    gripper_position_pub_->publish(msg);
    if (future.wait_for(std::chrono::seconds(5)) == std::future_status::timeout)
      RCLCPP_WARN(this->get_logger(), "openGripper timed out");
    else
      RCLCPP_INFO(this->get_logger(), "Gripper opened");
  }

  void closeGripper()
  {
    gripper_pick_on_promise_ = std::make_shared<std::promise<bool>>();
    auto future = gripper_pick_on_promise_->get_future();
    rm_ros_interfaces::msg::Gripperpick msg;
    msg.speed = 200;
    msg.force = 200;
    msg.block = true;
    gripper_pick_on_pub_->publish(msg);
    if (future.wait_for(std::chrono::seconds(5)) == std::future_status::timeout)
      RCLCPP_WARN(this->get_logger(), "closeGripper timed out");
    else
      RCLCPP_INFO(this->get_logger(), "Gripper closed");
  }

  // ---------------------------------------------------------------------------
  // Gripper result callbacks — called from spin thread, fulfill promises
  // ---------------------------------------------------------------------------
  void gripperPositionResultCallback(const std_msgs::msg::Bool::SharedPtr msg)
  {
    if (gripper_position_promise_)
    {
      gripper_position_promise_->set_value(msg->data);
      gripper_position_promise_.reset();
    }
  }

  void gripperPickOnResultCallback(const std_msgs::msg::Bool::SharedPtr msg)
  {
    if (gripper_pick_on_promise_)
    {
      gripper_pick_on_promise_->set_value(msg->data);
      gripper_pick_on_promise_.reset();
    }
  }

  // ---------------------------------------------------------------------------
  // TF2: transform pose from camera_color_optical_frame to base_link
  // For each frame, a transformation request is tried, if it fails,
  // the transformToBase flag returns false
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

  // Subscriptions / publishers
  rclcpp::Subscription<rm_ros_interfaces::msg::GraspCandidateArray>::SharedPtr grasp_sub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperset>::SharedPtr gripper_position_pub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperpick>::SharedPtr gripper_pick_on_pub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr gripper_position_result_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr gripper_pick_on_result_sub_;

  // Worker thread
  std::thread worker_thread_;
  std::queue<rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr> candidate_queue_;
  std::mutex queue_mutex_;
  std::condition_variable queue_cv_;
  bool shutdown_;

  // Gripper promises
  std::shared_ptr<std::promise<bool>> gripper_position_promise_;
  std::shared_ptr<std::promise<bool>> gripper_pick_on_promise_;
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