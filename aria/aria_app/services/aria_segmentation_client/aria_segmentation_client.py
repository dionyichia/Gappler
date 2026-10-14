#!/usr/bin/env python3
"""The aria client of the segmentation service (T2.1, minimal).

Turns what you say into what the arm looks for: a word on /aria/audio/prompt becomes a Target
on /grasp/target, which the grasp segmentation client reads. The stop word clears it.
Each word also sends /manipulator/grasp_request, which opens the state machine's trigger gate
(T1.25), so every time you ask is one grasp (T2.6). The stop word sends none.

Every word is sent, even a repeat, and /grasp/target is not latched. So if the grasp client
restarts, it looks for nothing until you say the word again: a restart never resumes an old
command on its own (Dion, 2026-10-13).

This first version sends the word only. After T2.2 (glasses image back on) it will also segment
the glasses image with the service, pick the object you look at, and send its crop as the
Target's reference. Gaze is in the raw glasses camera's pixels, so it must be rotated and
undistorted first (NEXT_STEPS 2.2).

    source aria/aria_env.sh && source install/local_setup.bash
    python aria/aria_app/services/aria_segmentation_client/aria_segmentation_client.py
"""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from segmentation_interfaces.msg import Target
from std_msgs.msg import Empty, String

from config import AudioStreamingPipelineConfig, ROS2Topics

STOP_KEYWORD = AudioStreamingPipelineConfig.STOP_KEYWORD


class AriaSegmentationClient(Node):
    def __init__(self):
        super().__init__("aria_segmentation_client")
        self.create_subscription(
            String, ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value, self.on_prompt, 10)
        self.target_pub = self.create_publisher(Target, ROS2Topics.GRASP_TARGET.value, 10)
        self.request_pub = self.create_publisher(
            Empty, ROS2Topics.MANIPULATOR_GRASP_REQUEST.value, 10)
        self.get_logger().info(
            f"Aria segmentation client ready: {ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value} "
            f"-> {ROS2Topics.GRASP_TARGET.value}")

    def on_prompt(self, msg: String):
        words = msg.data.strip().lower()
        if not words:
            return
        new = "" if words == STOP_KEYWORD else words
        target = Target(prompt=new)
        target.header.stamp = self.get_clock().now().to_msg()
        self.target_pub.publish(target)
        if new:
            self.request_pub.publish(Empty())
        self.get_logger().info(f"Target: {new!r}, grasp requested" if new else "Target cleared")


def main():
    rclpy.init()
    node = AriaSegmentationClient()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):   # Ctrl-C
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
