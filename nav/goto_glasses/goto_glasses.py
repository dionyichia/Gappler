#!/usr/bin/env python3
"""
goto_glasses.py
---------------
Handles all user-directed navigation in the pipeline.

OUTBOUND (verbal command → robot goes to user):
  Triggered by /aria/audio/prompt or manually via /goto_glasses/trigger.
  Robot navigates to 0.6 m left of the user, facing same direction.
  Saves user pose as _saved_user_pose for the return trip.

RETURN (manipulation done → robot returns to user):
  Triggered by /manipulator/return_to_user (Bool, true) from the manipulation team.
   Robot navigates to face the user with the D455 depth origin 0.5 m horizontally from user.
  Publishes result to /return_to_user/goal_reached ("success"/"failed").

Manual testing:
  Outbound : ros2 topic pub --once /goto_glasses/trigger std_msgs/msg/Empty {}
  Return   : ros2 topic pub --once /manipulator/return_to_user std_msgs/msg/Bool '{data: true}'
  Cancel   : ros2 topic pub --once /goto_glasses/cancel std_msgs/msg/Empty {}
"""

import math
from gappler_common import camera_reference_frame, config
from nav_geometry import camera_goal_xy

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.time import Time
from scipy.spatial.transform import Rotation
from std_msgs.msg import Bool, Empty, String
from tf2_ros import Buffer, TransformException, TransformListener

# shared/global_config.yaml and nav/nav_config.yaml (goto_glasses)
CFG = config("nav", "goto_glasses")
TOPICS = CFG["topics"]
SIDE_OFFSET_M = CFG["side_offset_m"]  # metres to the left of the user (outbound leg)
RETURN_CLEARANCE = CFG["return_clearance_m"]  # metres, horizontal D455 depth-origin to user
CAMERA_FRAME = camera_reference_frame()


class GotoGlasses(Node):
    def __init__(self):
        super().__init__("goto_glasses")
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._glasses_pose: PoseStamped | None = None
        self._saved_user_pose: PoseStamped | None = None  # snapshotted at trigger time
        self._navigating: bool = False  # outbound nav in progress
        self._returning: bool = False  # return nav in progress
        self._goal_handle = None  # active Nav2 goal handle for cancellation

        self.create_subscription(
            PoseStamped, TOPICS["fused_pose"], self._on_glasses_pose, 10
        )
        # Outbound: manual trigger for testing
        self.create_subscription(
            Empty, TOPICS["goto_glasses_trigger"], self._on_manual_trigger, 10
        )
        # Emergency cancel: kills any active navigation goal
        self.create_subscription(
            Empty, TOPICS["goto_glasses_cancel"], self._on_cancel_trigger, 10
        )
        # Outbound: auto-trigger from verbal command
        self.create_subscription(
            String, TOPICS["audio_transcription_prompt"], self._on_audio_prompt, 10
        )
        # Return: triggered by manipulation team when grasp is complete
        self.create_subscription(
            Bool, TOPICS["manipulator_return_to_user"], self._on_manipulation_done, 10
        )

        self._nav_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self._return_result_pub = self.create_publisher(
            String, TOPICS["return_to_user_goal_reached"], 10
        )

        self.get_logger().info(
            "GotoGlasses ready. Waiting for /aria/fused_pose (look at ArUco marker first).\n"
            "  Manual outbound: ros2 topic pub --once /goto_glasses/trigger std_msgs/msg/Empty {}\n"
            "  Manual return  : ros2 topic pub --once /manipulator/return_to_user std_msgs/msg/Bool '{data: true}'"
        )

    # ── callbacks ─────────────────────────────────────────────────────────────

    def _on_glasses_pose(self, msg: PoseStamped) -> None:
        """Store the latest glasses pose. Called on every VIO update."""
        self._glasses_pose = msg
        self.get_logger().info(
            f"Glasses pose: x={msg.pose.position.x:.2f} y={msg.pose.position.y:.2f}",
            throttle_duration_sec=2.0,
        )

    def _on_audio_prompt(self, msg: String) -> None:
        """Auto-trigger navigation when user gives a verbal object command."""
        object_name = msg.data.strip()
        print(object_name)
        if not object_name:
            return
        if object_name.lower() == "end":
            self._cancel_navigation()
            return
        self.get_logger().info(
            f"Audio command received: '{object_name}' — navigating to user."
        )
        self._trigger_navigation()

    def _on_manual_trigger(self, _: Empty) -> None:
        """Manual trigger via /goto_glasses/trigger for testing."""
        self.get_logger().info("Manual trigger received.")
        self._trigger_navigation()

    def _on_cancel_trigger(self, _: Empty) -> None:
        """Manual cancel via /goto_glasses/cancel — kills any active nav goal."""
        self.get_logger().info("Cancel trigger received.")
        self._cancel_navigation()

    def _on_manipulation_done(self, msg: Bool) -> None:
        """Triggered by manipulation team — navigate back to the saved user position."""
        if not msg.data:
            return
        if self._returning:
            self.get_logger().warn("Return ignored — already returning to user.")
            return
        if self._navigating:
            self.get_logger().warn(
                "Return ignored — outbound navigation still in progress."
            )
            return
        if self._saved_user_pose is None:
            self.get_logger().warn("Return ignored — no saved user pose available.")
            return

        try:
            goal_pose = self._compute_return_goal(self._saved_user_pose)
        except (TransformException, ValueError) as e:
            self.get_logger().warn(f"Camera return geometry unavailable; refusing return: {e}")
            return
        self._returning = True
        self.get_logger().info(
            f"Manipulation done. Returning to user. Goal: "
            f"x={goal_pose.pose.position.x:.2f} y={goal_pose.pose.position.y:.2f}"
        )
        self._send_nav_goal(goal_pose)

    def _trigger_navigation(self) -> None:
        """Shared navigation logic for both audio and manual triggers."""
        if self._glasses_pose is None:
            self.get_logger().warn("Trigger ignored — no glasses pose available yet.")
            return
        if self._navigating:
            self.get_logger().warn("Trigger ignored — navigation already in progress.")
            return

        # Snapshot the user's pose at this exact moment for navigation + return trip
        self._saved_user_pose = self._glasses_pose
        self._navigating = True

        ux = self._saved_user_pose.pose.position.x
        uy = self._saved_user_pose.pose.position.y
        goal_pose = self._compute_goal(self._saved_user_pose)
        self.get_logger().info(
            f"Aria Glasses position: x={ux:.3f} y={uy:.3f}\n"
            f"  → Navigating to goal: x={goal_pose.pose.position.x:.3f} "
            f"y={goal_pose.pose.position.y:.3f} (0.6 m left of user)"
        )
        self._send_nav_goal(goal_pose)

    # ── geometry ──────────────────────────────────────────────────────────────

    def _compute_goal(self, glasses_pose: PoseStamped) -> PoseStamped:
        """
        Place the robot SIDE_OFFSET_M to the left of the glasses wearer,
        facing the same direction.

        'Left' is relative to the glasses wearer's facing direction (yaw):
          offset_x = -sin(yaw) * SIDE_OFFSET_M
          offset_y =  cos(yaw) * SIDE_OFFSET_M
        """
        q = glasses_pose.pose.orientation
        yaw = Rotation.from_quat([q.x, q.y, q.z, q.w]).as_euler("xyz")[2]

        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = (
            glasses_pose.pose.position.x - math.sin(yaw) * SIDE_OFFSET_M
        )
        goal.pose.position.y = (
            glasses_pose.pose.position.y + math.cos(yaw) * SIDE_OFFSET_M
        )
        goal.pose.position.z = 0.0
        goal.pose.orientation = glasses_pose.pose.orientation  # same facing direction
        return goal

    def _compute_return_goal(self, glasses_pose: PoseStamped) -> PoseStamped:
        """
        Stop with the D455 depth origin RETURN_CLEARANCE horizontally from the
        user, facing toward them. Both forward and lateral TF offsets matter.

        The stop point is placed in the direction the user is facing so the
        robot ends up facing them. Nav2 plans whatever path avoids obstacles.

          robot_yaw = user_yaw + π  (facing back at the user)
        """
        q = glasses_pose.pose.orientation
        yaw = Rotation.from_quat([q.x, q.y, q.z, q.w]).as_euler("xyz")[2]

        offset = self._tf_buffer.lookup_transform(
            "robot_base_link", CAMERA_FRAME, Time()
        ).transform.translation
        facing = yaw + math.pi
        goal_x, goal_y = camera_goal_xy(
            glasses_pose.pose.position.x, glasses_pose.pose.position.y,
            facing, offset.x, offset.y, RETURN_CLEARANCE,
        )

        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = goal_x
        goal.pose.position.y = goal_y
        goal.pose.position.z = 0.0

        # Robot faces opposite to the user's yaw (i.e. looks at the user)
        rq = Rotation.from_euler("z", facing).as_quat()
        goal.pose.orientation.x = float(rq[0])
        goal.pose.orientation.y = float(rq[1])
        goal.pose.orientation.z = float(rq[2])
        goal.pose.orientation.w = float(rq[3])
        return goal

    # ── nav2 ──────────────────────────────────────────────────────────────────

    def _send_nav_goal(self, pose: PoseStamped) -> None:
        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available.")
            self._navigating = False
            return
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose = pose
        future = self._nav_client.send_goal_async(nav_goal)
        future.add_done_callback(self._on_goal_accepted)

    def _cancel_navigation(self) -> None:
        """Cancel any active Nav2 goal and reset navigation state."""
        if self._goal_handle is not None:
            self.get_logger().warn(
                "End command received — cancelling active navigation."
            )
            self._goal_handle.cancel_goal_async()
            self._goal_handle = None
        else:
            self.get_logger().info(
                "End command received — no active navigation to cancel."
            )
        self._navigating = False
        self._returning = False

    def _on_goal_accepted(self, future) -> None:
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Nav2 rejected the goal.")
            self._navigating = False
            self._returning = False
            return
        self._goal_handle = goal_handle
        goal_handle.get_result_async().add_done_callback(self._on_nav_result)

    def _on_nav_result(self, future) -> None:
        status = future.result().status
        succeeded = status == 4  # STATUS_SUCCEEDED
        self._goal_handle = None

        if self._returning:
            self._returning = False
            result_msg = String()
            result_msg.data = "success" if succeeded else "failed"
            self._return_result_pub.publish(result_msg)
            if succeeded:
                self.get_logger().info(
                    "Return to user complete. Published to /return_to_user/goal_reached."
                )
            else:
                self.get_logger().warn(f"Return navigation failed (status {status}).")
        else:
            self._navigating = False
            if succeeded:
                self.get_logger().info("Outbound navigation to user complete.")
            else:
                self.get_logger().warn(f"Outbound navigation failed (status {status}).")


def main() -> None:
    rclpy.init()
    rclpy.spin(GotoGlasses())


if __name__ == "__main__":
    main()
