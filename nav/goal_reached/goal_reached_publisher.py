#!/usr/bin/env python3
"""
goal_reached_publisher.py
-------------------------
Bridges /goal_pose (PoseStamped) to the Nav2 NavigateToPose action server.

Subscribes to /goal_pose, forwards it as a Nav2 action goal, then publishes
the outcome to /goal_reached ("success" or "failed").

Topics
------
  Subscribed : /goal_pose    (geometry_msgs/PoseStamped)
  Published  : /goal_reached (std_msgs/String) — "success" or "failed"
"""

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String


class GoalReachedPublisher(Node):
    def __init__(self) -> None:
        super().__init__("goal_reached_publisher")
        self._publisher = self.create_publisher(String, "/goal_reached", 10)
        self._action_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self.create_subscription(PoseStamped, "/goal_pose", self._on_goal_pose, 10)
        self.get_logger().info("GoalReachedPublisher ready.")

    def _on_goal_pose(self, msg: PoseStamped) -> None:
        self.get_logger().info("Received goal pose — sending to Nav2.")
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = msg
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available — dropping goal.")
            return
        future = self._action_client.send_goal_async(goal_msg)
        future.add_done_callback(self._on_goal_accepted)

    def _on_goal_accepted(self, future) -> None:
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn("Goal rejected by Nav2.")
            return
        self.get_logger().info("Goal accepted — navigating.")
        goal_handle.get_result_async().add_done_callback(self._on_nav_result)

    def _on_nav_result(self, future) -> None:
        status = future.result().status
        outcome = "success" if status == 4 else "failed"
        msg = String()
        msg.data = outcome
        self._publisher.publish(msg)
        self.get_logger().info(f"Navigation result: {outcome}")


def main() -> None:
    rclpy.init()
    rclpy.spin(GoalReachedPublisher())


if __name__ == "__main__":
    main()
