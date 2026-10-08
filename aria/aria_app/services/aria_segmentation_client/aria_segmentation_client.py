#!/usr/bin/env python3
"""The aria client of the segmentation service (T2.1, minimal).

Turns what you say into what the arm looks for: a word on /aria/audio/prompt becomes a Target
on /grasp/target, which the grasp segmentation client reads. The stop word clears it.

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
from std_msgs.msg import String

from config import AudioStreamingPipelineConfig, ROS2Topics

STOP_KEYWORD = AudioStreamingPipelineConfig.STOP_KEYWORD


class AriaSegmentationClient(Node):
    def __init__(self):
        super().__init__("aria_segmentation_client")
        self.prompt = ""
        self.create_subscription(
            String, ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value, self.on_prompt, 10)
        self.target_pub = self.create_publisher(Target, ROS2Topics.GRASP_TARGET.value, 10)
        self.get_logger().info(
            f"Aria segmentation client ready: {ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value} "
            f"-> {ROS2Topics.GRASP_TARGET.value}")

    def on_prompt(self, msg: String):
        words = msg.data.strip().lower()
        if not words:
            return
        new = "" if words == STOP_KEYWORD else words
        if new == self.prompt:
            return
        self.prompt = new
        target = Target(prompt=new)
        target.header.stamp = self.get_clock().now().to_msg()
        self.target_pub.publish(target)
        self.get_logger().info(f"Target: {new!r}" if new else "Target cleared")


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
