#!/usr/bin/env python3
"""
goal_reached_publisher.py
-------------------------
Bridges /goal_pose (PoseStamped) to the Nav2 NavigateToPose action server.

Subscribes to /goal_pose, forwards it as a Nav2 action goal, then publishes
the outcome to /goal_reached ("success" or "failed").

Every goal gets exactly one answer. "failed" also covers the cases where the
goal never got going: Nav2 not available, the goal rejected, or an error while
sending it. It also covers an accepted goal that never reports back: Nav2 gone
from the network, or no result within result_timeout_s (the goal is cancelled
first). object_approach_node waits for this answer before it acts on the next
object, so staying silent would leave it waiting forever (CODE_AUDIT F1).

Topics
------
  Subscribed : /goal_pose    (geometry_msgs/PoseStamped)
  Published  : /goal_reached (std_msgs/String) — "success" or "failed"
"""

import time

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String
from gappler_common import config

# shared/global_config.yaml and nav/nav_config.yaml (goal_reached_publisher)
CFG = config("nav", "goal_reached_publisher")
TOPICS = CFG["topics"]
RESULT_TIMEOUT = float(CFG["result_timeout_s"])  # seconds
# Checks in a row (one per second) that must find Nav2 gone before a goal is failed.
# One missed check can be a discovery hiccup.
SERVER_GONE_CHECKS = 3


class GoalReachedPublisher(Node):
    def __init__(self) -> None:
        super().__init__("goal_reached_publisher")
        self._publisher = self.create_publisher(String, TOPICS["goal_reached"], 10)
        self._action_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self.create_subscription(PoseStamped, TOPICS["goal_pose"], self._on_goal_pose, 10)
        # Accepted goals still waiting for a result. Each is a dict:
        # handle, deadline (time.monotonic), gone (checks that found no Nav2), answered.
        self._pending: list[dict] = []
        self.create_timer(1.0, self._check_pending)
        self.get_logger().info("GoalReachedPublisher ready.")

    def _on_goal_pose(self, msg: PoseStamped) -> None:
        self.get_logger().info("Received goal pose — sending to Nav2.")
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = msg
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available — goal failed.")
            self._publish_outcome("failed")
            return
        future = self._action_client.send_goal_async(goal_msg)
        future.add_done_callback(self._on_goal_accepted)

    def _on_goal_accepted(self, future) -> None:
        try:
            goal_handle = future.result()
        except Exception as e:  # a failed send must still answer (CODE_AUDIT F1)
            self.get_logger().error(f"Sending the goal to Nav2 failed: {e}")
            self._publish_outcome("failed")
            return
        if not goal_handle.accepted:
            self.get_logger().warn("Goal rejected by Nav2.")
            self._publish_outcome("failed")
            return
        self.get_logger().info("Goal accepted — navigating.")
        pending = {"handle": goal_handle, "deadline": time.monotonic() + RESULT_TIMEOUT,
                   "gone": 0, "answered": False}
        self._pending.append(pending)
        goal_handle.get_result_async().add_done_callback(
            lambda future: self._on_nav_result(future, pending)
        )

    def _on_nav_result(self, future, pending: dict) -> None:
        try:
            status = future.result().status
        except Exception as e:
            self.get_logger().error(f"Reading the Nav2 result failed: {e}")
            status = None
        self._answer(pending, "success" if status == 4 else "failed")

    def _check_pending(self) -> None:
        """Fail an accepted goal that can no longer report back, so it still gets its
        one answer (CODE_AUDIT F1): Nav2 gone, or no result within RESULT_TIMEOUT."""
        server_up = self._action_client.server_is_ready() if self._pending else True
        for pending in self._pending:
            if pending["answered"]:
                continue
            pending["gone"] = 0 if server_up else pending["gone"] + 1
            if pending["gone"] >= SERVER_GONE_CHECKS:
                self.get_logger().error("Nav2 went away during navigation — goal failed.")
            elif time.monotonic() > pending["deadline"]:
                self.get_logger().error(
                    f"No result from Nav2 in {RESULT_TIMEOUT:.0f} s — cancelling, goal failed."
                )
                # Stop the base before saying "failed": the approach node may send a new goal.
                pending["handle"].cancel_goal_async()
            else:
                continue
            self._answer(pending, "failed")
        self._pending = [p for p in self._pending if not p["answered"]]

    def _answer(self, pending: dict, outcome: str) -> None:
        """Publish one accepted goal's outcome, the first time only. A result that
        arrives after the check above has failed the goal is dropped."""
        if pending["answered"]:
            return
        pending["answered"] = True
        self._publish_outcome(outcome)

    def _publish_outcome(self, outcome: str) -> None:
        msg = String()
        msg.data = outcome
        self._publisher.publish(msg)
        self.get_logger().info(f"Navigation result: {outcome}")


def main() -> None:
    rclpy.init()
    node = GoalReachedPublisher()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass  # Ctrl+C: exit quietly (CODE_AUDIT F4)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
