#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include <moveit/move_group_interface/move_group_interface.h>

class Manipulator : public rclcpp::Node
{
public:
    Manipulator() : Node("manipulator")
    {
        // Create MoveIt interface for the arm planning group
        move_group_ = std::make_shared<moveit::planning_interface::MoveGroupInterface>(
            shared_from_this(),
            "rm_group" // Planning group name from SRDF - check yours
        );

        subscription_ = this->create_subscription<geometry_msgs::msg::PoseStamped>(
            "/object_pose", 10,
            std::bind(&Manipulator::pose_callback, this, std::placeholders::_1));

        RCLCPP_INFO(this->get_logger(), "Node base initialized. Waiting for MoveGroup setup...");
    }

    // New initialization function
    void setup_moveit()
    {
        move_group_ = std::make_shared<moveit::planning_interface::MoveGroupInterface>(
            shared_from_this(),
            "rm_group");
        RCLCPP_INFO(this->get_logger(), "MoveIt 2 Interface initialized for group: rm_group");
    }

private:
    void pose_callback(const geometry_msgs::msg::PoseStamped::SharedPtr msg)
    {
        RCLCPP_INFO(this->get_logger(), "Received target pose, planning...");

        // Set the target pose
        move_group_->setPoseTarget(*msg);

        // Plan the motion
        moveit::planning_interface::MoveGroupInterface::Plan plan;
        bool success = (move_group_->plan(plan) == moveit::core::MoveItErrorCode::SUCCESS);

        if (success)
        {
            RCLCPP_INFO(this->get_logger(), "Plan successful, executing...");
            move_group_->execute(plan);
        }
        else
        {
            RCLCPP_ERROR(this->get_logger(), "Planning failed!");
        }
    }

    std::shared_ptr<moveit::planning_interface::MoveGroupInterface> move_group_;
    rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr subscription_;
};

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<Manipulator>();

    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}