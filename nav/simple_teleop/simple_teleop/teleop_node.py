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

Publishes cmd_vel at 10 Hz so the robot keeps moving while a key is held.
"""

import select
import sys
import termios
import tty

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class SimpleTeleop(Node):
    def __init__(self) -> None:
        super().__init__("simple_teleop")
        self._pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.create_timer(0.1, self._publish_velocity)

        self.linear_x = 0.0
        self.angular_z = 0.0
        self._speed = 0.3   # m/s
        self._turn = 0.5    # rad/s

        self.get_logger().info(
            "Simple Teleop for Echo Plus  |  W/S Forward/Back  A/D Turn  X Stop  Q Quit"
        )

    def _publish_velocity(self) -> None:
        twist = Twist()
        twist.linear.x = self.linear_x
        twist.angular.z = self.angular_z
        self._pub.publish(twist)

    def update_velocity(self, key: str) -> bool:
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


def _get_key(settings) -> str:
    tty.setraw(sys.stdin.fileno())
    select.select([sys.stdin], [], [], 0)
    key = sys.stdin.read(1)
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key.lower()


def main() -> None:
    settings = termios.tcgetattr(sys.stdin)
    rclpy.init()
    node = SimpleTeleop()
    try:
        while rclpy.ok():
            if not node.update_velocity(_get_key(settings)):
                break
            rclpy.spin_once(node, timeout_sec=0.01)
    except Exception as e:
        print(e)
    finally:
        node.linear_x = 0.0
        node.angular_z = 0.0
        node._publish_velocity()
        node.destroy_node()
        rclpy.shutdown()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)


if __name__ == "__main__":
    main()
