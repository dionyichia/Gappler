#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <rm_ros_interfaces/msg/gripperpick.hpp>
#include <rm_ros_interfaces/msg/gripperset.hpp>
#include <rm_ros_interfaces/msg/grasp_candidate_array.hpp>
#include "rm_mtc/mtc_planner.hpp"
#include <std_msgs/msg/bool.hpp>
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
    // Create State Machine instance and shared pointer for MTC planner
    node->mtc_planner_ = std::make_shared<MtcPlanner>(node);
    return node;
  }

private:
  GraspStateMachine()
      : Node("grasp_state_machine",
             rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true)),
        state_(State::IDLE),
        tf_buffer_(this->get_clock()),
        tf_listener_(tf_buffer_)
  {
    // Subscriber: top 5 pre-sorted grasp candidates
    grasp_sub_ = this->create_subscription<rm_ros_interfaces::msg::GraspCandidateArray>(
        "/grasp_candidates", 10,
        std::bind(&GraspStateMachine::graspCallback, this, std::placeholders::_1));

    // Publisher: gripper commands
    gripper_position_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperset>(
        "/rm_driver/set_gripper_position_cmd", 10);
    gripper_pick_on_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperpick>(
        "/rm_driver/set_gripper_pick_on_cmd", 10);

    // Publisher: gripper status
    gripper_position_result_sub_ = this->create_subscription<std_msgs::msg::Bool>(
        "/rm_driver/set_gripper_position_result", 10,
        std::bind(&GraspStateMachine::gripperPositionResultCallback, this, std::placeholders::_1));

    gripper_pick_on_result_sub_ = this->create_subscription<std_msgs::msg::Bool>(
        "/rm_driver/set_gripper_pick_on_result", 10,
        std::bind(&GraspStateMachine::gripperPickOnResultCallback, this, std::placeholders::_1));

    RCLCPP_INFO(this->get_logger(), "Grasp state machine ready. State: IDLE");
  }
  // ---------------------------------------------------------------------------
  // Gripper helpers
  // ---------------------------------------------------------------------------
  // Edit to use Gripperset
  void openGripper()
  {
    gripper_position_result_ = false;
    rm_ros_interfaces::msg::Gripperset msg;
    msg.position = 1000; // fully open (0-1000 maps to 0-70mm)
    msg.block = true;
    gripper_position_pub_->publish(msg);
    auto start = this->now();
    while (!gripper_position_result_)
    {
      rclcpp::spin_some(this->get_node_base_interface());
      if ((this->now() - start).seconds() > 5.0)
      {
        RCLCPP_WARN(this->get_logger(), "openGripper timed out");
        return;
      }
    }
    RCLCPP_INFO(this->get_logger(), "Gripper open command sent");
  }

  // Edit to use Gripper_Pick_On
  void closeGripper()
  {
    gripper_pick_on_result_ = false;
    rm_ros_interfaces::msg::Gripperpick msg;
    msg.speed = 200;
    msg.force = 200;
    msg.block = true;
    gripper_pick_on_pub_->publish(msg);
    auto start = this->now();
    while (!gripper_pick_on_result_)
    {
      rclcpp::spin_some(this->get_node_base_interface());
      if ((this->now() - start).seconds() > 5.0)
      {
        RCLCPP_WARN(this->get_logger(), "closeGripper timed out");
        return;
      }
    }
    RCLCPP_INFO(this->get_logger(), "Gripper close command sent");
  }

  void gripperPositionResultCallback(const std_msgs::msg::Bool::SharedPtr msg)
  {
    gripper_position_result_ = msg->data;
  }

  void gripperPickOnResultCallback(const std_msgs::msg::Bool::SharedPtr msg)
  {
    gripper_pick_on_result_ = msg->data;
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
      tf_buffer_.transform(stamped_in, stamped_out, "base_link",
                           tf2::durationFromSec(1.0));
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
  // Grasp candidate callback
  // ---------------------------------------------------------------------------
  void graspCallback(const rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg)
  {
    if (state_ != State::IDLE) // Ensuring that only one candidate is assessed at a time
    {
      RCLCPP_DEBUG(this->get_logger(), "Busy, ignoring new candidates");
      return;
    }

    if (msg->grasps.empty())
    {
      RCLCPP_WARN(this->get_logger(), "Received empty grasp candidates");
      return;
    }

    RCLCPP_INFO(this->get_logger(), "IDLE → SELECTING (%zu candidates)", msg->grasps.size());
    state_ = State::SELECTING;

    // Candidates are pre-sorted by score, iterate highest first
    // Loop through candidates, attempt transform and MTC grasp, break on first success
    for (const auto &candidate : msg->grasps)
    {
      RCLCPP_INFO(this->get_logger(), "Trying candidate with score: %.4f", candidate.score);

      // Check if transform to base_link works
      geometry_msgs::msg::Pose pose_base;
      if (!transformToBase(candidate.pose, pose_base))
      {
        RCLCPP_WARN(this->get_logger(), "Transform failed, skipping candidate");
        continue;
      }

      // Attempt MTC grasp
      state_ = State::EXECUTING;
      RCLCPP_INFO(this->get_logger(), "SELECTING → EXECUTING");

      openGripper();

      if (!mtc_planner_->moveToPose(pose_base))
      {
        RCLCPP_WARN(this->get_logger(), "moveToPose failed, trying next candidate");
        state_ = State::SELECTING;
        continue;
      }
      // TODO: Implement check for Gripper open success before proceeding with MTC
      closeGripper();

      if (!mtc_planner_->moveToHome())
      {
        RCLCPP_ERROR(this->get_logger(), "moveToHome failed. EXECUTING → IDLE");
        state_ = State::IDLE;
        return;
      }

      RCLCPP_INFO(this->get_logger(), "Grasp succeeded. EXECUTING → IDLE");
      state_ = State::IDLE;
      return;
    }

    // All candidates failed
    RCLCPP_ERROR(this->get_logger(), "All candidates failed. SELECTING → IDLE");
    state_ = State::IDLE;
  }

  // ---------------------------------------------------------------------------
  // Members - essential variables outside of helper functions
  // ---------------------------------------------------------------------------
  bool gripper_position_result_{false};
  bool gripper_pick_on_result_{false};
  State state_;                            // Current state of the state machine
  tf2_ros::Buffer tf_buffer_;              // History of robot links
  tf2_ros::TransformListener tf_listener_; // Constant update of tf_buffer_
  std::shared_ptr<MtcPlanner> mtc_planner_;
  rclcpp::Subscription<rm_ros_interfaces::msg::GraspCandidateArray>::SharedPtr grasp_sub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperset>::SharedPtr gripper_position_pub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperpick>::SharedPtr gripper_pick_on_pub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr gripper_position_result_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr gripper_pick_on_result_sub_;
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