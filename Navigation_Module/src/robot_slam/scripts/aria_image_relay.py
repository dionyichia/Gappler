#!/usr/bin/env python3
"""
aria_image_relay.py
-------------------
Subscribes to the glasses CompressedImage feed (BEST_EFFORT QoS) and
republishes it as a raw sensor_msgs/Image so RViz can display it.
"""
import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image

BEST_EFFORT_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)


class AriaImageRelay(Node):
    def __init__(self):
        super().__init__("aria_image_relay")
        self._bridge = CvBridge()
        self.create_subscription(
            CompressedImage,
            "/aria/rgb_camera/undistorted",
            self._on_image,
            BEST_EFFORT_QOS,
        )
        self._pub = self.create_publisher(Image, "/aria/rgb_camera/view", 10)
        self.get_logger().info("AriaImageRelay started.")

    def _on_image(self, msg: CompressedImage) -> None:
        np_arr = np.frombuffer(msg.data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is None:
            return
        raw_msg = self._bridge.cv2_to_imgmsg(image, encoding="bgr8")
        raw_msg.header = msg.header
        self._pub.publish(raw_msg)


def main() -> None:
    rclpy.init()
    rclpy.spin(AriaImageRelay())


if __name__ == "__main__":
    main()
