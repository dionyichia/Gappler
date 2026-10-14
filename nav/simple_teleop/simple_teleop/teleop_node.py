#!/usr/bin/env python3
"""
teleop_node.py
--------------
Keyboard teleoperation for the Echo Plus robot.

Controls
--------
  W / S  — Forward / Backward
  A / D  — Turn Left / Right
  X      — Stop
  Q      — Quit

Publishes cmd_vel at 10 Hz; movement needs fresh repeated key events.
Silence returns requested velocity to zero, not a verified physical wheel stop.
"""

import select
import math
import os
import sys
import termios
import time
import tty

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions


class SimpleTeleop(Node):
    def __init__(self) -> None:
        super().__init__("simple_teleop")
        self._pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.create_timer(0.1, self._publish_velocity)

        self.linear_x = 0.0
        self.angular_z = 0.0
        self._speed = float(self.declare_parameter("speed", 0.05).value)  # m/s
        self._turn = float(self.declare_parameter("turn", 0.15).value)  # rad/s
        self._key_timeout = float(self.declare_parameter("key_timeout", 0.25).value)
        if not all(math.isfinite(value) and value >= 0 for value in (self._speed, self._turn)):
            raise ValueError("speed and turn must be finite and nonnegative")
        if not math.isfinite(self._key_timeout) or self._key_timeout <= 0:
            raise ValueError("key_timeout must be finite and positive")
        self._last_movement = time.monotonic()

        self.get_logger().info(
            "Simple Teleop for Echo Plus  |  W/S Forward/Back  A/D Turn  X Stop  Q Quit"
        )

    def _publish_velocity(self) -> None:
        if time.monotonic() - self._last_movement >= self._key_timeout:
            self.linear_x = 0.0
            self.angular_z = 0.0
        twist = Twist()
        twist.linear.x = self.linear_x
        twist.angular.z = self.angular_z
        self._pub.publish(twist)

    def update_velocity(self, key: str) -> bool:
        if key in ("w", "s", "a", "d"):
            self._last_movement = time.monotonic()
        if key == "w":
            self.linear_x = self._speed
            self.angular_z = 0.0
            self.get_logger().info("Forward")
        elif key == "s":
            self.linear_x = -self._speed
            self.angular_z = 0.0
            self.get_logger().info("Backward")
        elif key == "a":
            self.linear_x = 0.0
            self.angular_z = self._turn
            self.get_logger().info("Turn Left")
        elif key == "d":
            self.linear_x = 0.0
            self.angular_z = -self._turn
            self.get_logger().info("Turn Right")
        elif key == "x":
            self.linear_x = 0.0
            self.angular_z = 0.0
            self.get_logger().info("Stop")
        elif key == "q":
            self.get_logger().info("Quitting.")
            return False
        return True


def _get_key() -> str:
    """Bound the input wait so silence cannot starve the ROS publishing timer."""
    ready, _, _ = select.select([sys.stdin], [], [], 0.02)
    if not ready:
        return ""
    # Match select's descriptor-level readiness: TextIOWrapper can prefetch
    # later stop/quit keys and hide them from the next select call.
    key = os.read(sys.stdin.fileno(), 1).decode("ascii", errors="replace")
    if not key:
        raise EOFError("keyboard terminal disconnected")
    if key == "\x03":
        raise KeyboardInterrupt
    return key.lower()


def main() -> None:
    settings = termios.tcgetattr(sys.stdin)
    # Own SIGINT handling so the final zero is requested before ROS teardown.
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = None
    try:
        node = SimpleTeleop()
        tty.setraw(sys.stdin.fileno())
        while rclpy.ok():
            if not node.update_velocity(_get_key()):
                break
            rclpy.spin_once(node, timeout_sec=0.01)
    except KeyboardInterrupt:
        if node is not None:
            node.get_logger().info("Keyboard interrupt: requesting zero before exit")
    except EOFError as error:
        if node is not None:
            node.get_logger().warning(str(error))
    finally:
        try:
            if node is not None:
                node.linear_x = 0.0
                node.angular_z = 0.0
                if rclpy.ok():
                    node._publish_velocity()
                node.destroy_node()
            rclpy.try_shutdown()
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)


if __name__ == "__main__":
    main()
