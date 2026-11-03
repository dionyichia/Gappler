import logging

import numpy as np
import rclpy
from builtin_interfaces.msg import Time
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage

from config import VIDEO_QOS
from .image_helper import ImageHelper

logger = logging.getLogger(__name__)


def stamp_from_ns(ns: int) -> Time:
    """A ROS stamp from a time in nanoseconds, such as a glasses capture time (T2.19)."""
    return Time(sec=int(ns // 1_000_000_000), nanosec=int(ns % 1_000_000_000))


class ROSPublisher(Node):
    def __init__(
        self,
        node_name: str,
        msg_type: type,
        topic: str,
        qos_profile=VIDEO_QOS,
    ):
        if not rclpy.ok():
            rclpy.init()
        super().__init__(node_name)
        self.publisher = self.create_publisher(msg_type, topic, qos_profile)
        logger.debug(f"Publishing to {topic}")

    def publish(self, msg):
        self.publisher.publish(msg)

    def publish_image(self, image: np.ndarray, stamp_ns: int = None):
        """stamp_ns: when the image was captured. Without it, the computer's time now."""
        msg = CompressedImage()
        msg.header.stamp = (self.get_clock().now().to_msg() if stamp_ns is None
                            else stamp_from_ns(stamp_ns))
        msg.format = "jpeg"

        msg.data = ImageHelper.compress_image(image)[1]

        self.publisher.publish(msg)
