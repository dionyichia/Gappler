#!/usr/bin/env python3
"""
Emergency stop utility for RM65.
Run in a separate terminal before any hardware motion test.

  E       — emergency stop  (rm_driver/emergency_stop_cmd, state=true)
  R       — resume          (rm_driver/emergency_stop_cmd, state=false)
  S       — soft stop       (rm_driver/move_stop_cmd, current motion only)
  Q       — quit this script (the only way out that does not send a stop)
  Ctrl+C  — emergency stop, then quit

Closing the terminal, or kill / kill -INT from outside, also sends an emergency stop.
Every stop is confirmed by the driver's subscription before the script exits.
"""

import os
import signal
import sys
import termios

import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rm_ros_interfaces.msg import Stop
from std_msgs.msg import Empty

CTRL_C = "\x03"
ACK_WAIT = Duration(seconds=1.0)  # how long to wait for subscribers to confirm the last stop


class EStop(Node):
    def __init__(self):
        super().__init__("estop")
        self.estop_pub = self.create_publisher(Stop, "/rm_driver/emergency_stop_cmd", 1)
        self.move_stop_pub = self.create_publisher(Empty, "/rm_driver/move_stop_cmd", 1)
        self.get_logger().info(
            "E-stop ready.  E=emergency  R=resume  S=soft stop  Q=quit  Ctrl+C=emergency and quit"
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

    def wait_delivered(self):
        """publish() only queues the message. Wait for every subscriber to confirm it, so shutting
        down straight after cannot lose the stop (CODE_AUDIT B2)."""
        self.estop_pub.wait_for_all_acked(ACK_WAIT)
        self.move_stop_pub.wait_for_all_acked(ACK_WAIT)


class Signalled(Exception):
    pass


def on_signal(signum, _frame):
    raise Signalled(signal.Signals(signum).name)


def keys(fd):
    """Yield one lower-case key at a time until the terminal closes.

    The terminal is switched to key-at-a-time mode once, not once per key. Switching per key threw
    away any key typed in between, so S then E pressed fast could lose the e-stop (CODE_AUDIT B2c).
    Signal generation is off, so Ctrl+C arrives as a key and is handled here (CODE_AUDIT B2a).
    """
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG)
    new[6][termios.VMIN], new[6][termios.VTIME] = 1, 0
    termios.tcsetattr(fd, termios.TCSANOW, new)   # TCSANOW: keep anything already typed
    try:
        while True:
            b = os.read(fd, 1)
            if not b:
                return
            yield b.decode(errors="ignore").lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main():
    # rclpy's own SIGINT handler shuts ROS down before a stop can be sent (CODE_AUDIT B2).
    # Turn it off and handle the signals here instead.
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = EStop()
    for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(s, on_signal)

    quit_cleanly = False
    try:
        for key in keys(sys.stdin.fileno()):
            if key == "e":
                node.emergency_stop()
            elif key == "r":
                node.resume()
            elif key == "s":
                node.soft_stop()
            elif key == "q":
                quit_cleanly = True
                break
            elif key == CTRL_C:
                break
    except Signalled as e:
        node.get_logger().warn(f"{e} received")
    finally:
        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(s, signal.SIG_IGN)      # nothing may interrupt the last stop
        if not quit_cleanly:                      # Ctrl+C, a signal, a closed terminal or an error
            node.emergency_stop()
        node.wait_delivered()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
