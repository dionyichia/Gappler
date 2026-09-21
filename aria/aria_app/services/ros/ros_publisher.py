import logging

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage

from config import VIDEO_QOS

logger = logging.getLogger(__name__)


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

    def publish_image(self, image: np.ndarray):
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.format = "jpeg"

        # Encode to JPEG — quality 80 is a good balance
        _, compressed = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        msg.data = compressed.tobytes()

        self.publisher.publish(msg)
