#!/usr/bin/env python3
"""
Dummy mask publisher for testing without SAM.
Subscribes to depth topic to match resolution and timestamp,
publishes an all-True mask on the SAM mask placeholder topic.
"""

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

# Match these to the placeholders in anygrasp_node.py
TOPIC_DEPTH = "/PLACEHOLDER/depth/image_rect_raw"
TOPIC_MASK = "/PLACEHOLDER/sam/mask"


class DummyMaskPublisher(Node):
    def __init__(self):
        super().__init__("dummy_mask_publisher")

        self.mask_pub = self.create_publisher(Image, TOPIC_MASK, 10)

        self.depth_sub = self.create_subscription(
            Image, TOPIC_DEPTH, self.depth_callback, 10
        )

        self.get_logger().info("Dummy mask publisher ready")

    def depth_callback(self, depth_msg: Image):
        mask_msg = Image()
        # Match header exactly so ApproximateTimeSynchronizer aligns them
        mask_msg.header = depth_msg.header
        mask_msg.height = depth_msg.height
        mask_msg.width = depth_msg.width
        mask_msg.encoding = "mono8"
        mask_msg.step = depth_msg.width
        # All-True mask: every pixel is part of the "object"
        mask_msg.data = bytes(
            np.ones(depth_msg.height * depth_msg.width, dtype=np.uint8)
        )
        self.mask_pub.publish(mask_msg)


def main():
    rclpy.init()
    node = DummyMaskPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
