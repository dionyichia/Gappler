#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <rm_ros_interfaces/msg/gripperpick.hpp>
#include <rm_ros_interfaces/msg/grasp_candidate_array.hpp>
#include "rm_mtc/mtc_planner.hpp"

// ---------------------------------------------------------------------------
// State definitions
// ---------------------------------------------------------------------------
enum class State { IDLE, SELECTING, EXECUTING }; 

// GraspStatemMachine is a ROS2 node
// Subscribes to grasp candidates topic and publishes to Gripperpick topic
// As a node, it has the ability to create publishers, subscribers, timers 
class GraspStateMachine : public rclcpp::Node
{
public:


private:
  GraspStateMachine()
  : Node("grasp_state_machine",
         rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true)),
    state_(State::IDLE),
    tf_buffer_(this->get_clock()),
    tf_listener_(tf_buffer_)
  {
    // MTC planner shares this node
    mtc_planner_ = std::make_shared<MtcPlanner>(shared_from_this());

    // Subscriber: top 5 pre-sorted grasp candidates
    grasp_sub_ = this->create_subscription<rm_ros_interfaces::msg::GraspCandidateArray>(
      "/grasp_candidates", 10,
      std::bind(&GraspStateMachine::graspCallback, this, std::placeholders::_1));

    // Publisher: gripper commands
    // Add additional gripper message 
    gripper_pub_ = this->create_publisher<rm_ros_interfaces::msg::Gripperpick>(
      "/rm_driver/set_gripper_pick_cmd", 10);

    RCLCPP_INFO(this->get_logger(), "Grasp state machine ready. State: IDLE");
  }


  // ---------------------------------------------------------------------------
  // Gripper helpers
  // ---------------------------------------------------------------------------
  // Edit to use Gripperset
  void openGripper()
  {`
    rm_ros_interfaces::msg::Gripperpick msg;
    msg.speed = 500;
    msg.force = 200;
    msg.block = true;
    gripper_pub_->publish(msg);
    RCLCPP_INFO(this->get_logger(), "Gripper open command sent");
  }

  // Edit to use Gripper_Pick_On 
  void closeGripper()
  {
    rm_ros_interfaces::msg::Gripperpick msg;
    msg.speed = 200;
    msg.force = 200;
    msg.block = true;
    gripper_pub_->publish(msg);
    RCLCPP_INFO(this->get_logger(), "Gripper close command sent");
  }

  // ---------------------------------------------------------------------------
  // TF2: transform pose from camera_color_optical_frame to base_link
  // For each frame, a transformation request is tried, if it fails, 
  // the transformToBase flag returns false
  // ---------------------------------------------------------------------------
  bool transformToBase(const geometry_msgs::msg::Pose& pose_in,
                       geometry_msgs::msg::Pose& pose_out)
  {
    geometry_msgs::msg::PoseStamped stamped_in, stamped_out;
    stamped_in.header.frame_id = "camera_color_optical_frame";
    stamped_in.header.stamp    = this->now();
    stamped_in.pose            = pose_in;

    try
    {
      tf_buffer_.transform(stamped_in, stamped_out, "base_link",
                           tf2::durationFromSec(1.0));
      pose_out = stamped_out.pose;
      return true;
    }
    catch (const tf2::TransformException& ex)
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
    for (const auto& candidate : msg->grasps)
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

      //TODO: Implement check for Gripper open success before proceeding with MTC
    
      // Blocking call, only proceeds if MTC plan and execution succeed
      bool success = mtc_planner_->executeGrasp(pose_base);

      if (success)
      {
        closeGripper();
        //TODO: Implement check for Gripper open success before proceeding with MTC
        RCLCPP_INFO(this->get_logger(), "Grasp succeeded. EXECUTING → IDLE");
      }
      else
      {
        RCLCPP_WARN(this->get_logger(), "MTC failed for this candidate, trying next");
        state_ = State::SELECTING;
        continue;
      }

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
  State state_; // Current state of the state machine
  tf2_ros::Buffer tf_buffer_; // History of robot links
  tf2_ros::TransformListener tf_listener_; // Constant update of tf_buffer_ 
  std::shared_ptr<MtcPlanner> mtc_planner_; 
  rclcpp::Subscription<rm_ros_interfaces::msg::GraspCandidateArray>::SharedPtr grasp_sub_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Gripperpick>::SharedPtr gripper_pub_;
};

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
int main(int argc, char** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<GraspStateMachine>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}