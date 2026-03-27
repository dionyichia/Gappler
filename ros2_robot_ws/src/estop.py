#!/usr/bin/env python3
"""
Emergency stop utility for RM65.
Run in a separate terminal before any hardware motion test.

  E  — emergency stop  (rm_driver/emergency_stop_cmd, state=true)
  R  — resume          (rm_driver/emergency_stop_cmd, state=false)
  S  — soft stop       (rm_driver/move_stop_cmd, current motion only)
  Q  — quit this script
"""

import sys
import termios
import tty

import rclpy
from rclpy.node import Node
from rm_ros_interfaces.msg import Stop
from std_msgs.msg import Empty


class EStop(Node):
    def __init__(self):
        super().__init__("estop")
        self.estop_pub = self.create_publisher(Stop, "/rm_driver/emergency_stop_cmd", 1)
        self.move_stop_pub = self.create_publisher(Empty, "/rm_driver/move_stop_cmd", 1)
        self.get_logger().info(
            "E-stop ready.  E=emergency  R=resume  S=soft stop  Q=quit"
        )

    def emergency_stop(self):
        msg = Stop()
        msg.state = True
        self.estop_pub.publish(msg)
        self.get_logger().warn("EMERGENCY STOP SENT")

    def resume(self):
        msg = Stop()
        msg.state = False
        self.estop_pub.publish(msg)
        self.get_logger().info("Resume sent")

    def soft_stop(self):
        self.move_stop_pub.publish(Empty())
        self.get_logger().info("Soft stop sent")


def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main():
    rclpy.init()
    node = EStop()
    try:
        while True:
            key = getch().lower()
            if key == "e":
                node.emergency_stop()
            elif key == "r":
                node.resume()
            elif key == "s":
                node.soft_stop()
            elif key == "q":
                break
    except KeyboardInterrupt:
        node.emergency_stop()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
