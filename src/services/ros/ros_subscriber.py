import logging

import rclpy
from rclpy.node import Node

from config import ROS2Config

logger = logging.getLogger(__name__)


class ROSSubscriber(Node):
    def __init__(self, node_name: str):
        if not rclpy.ok():
            rclpy.init()
        super().__init__(node_name)

    def subscribe(
        self, msg_type: type, topic: str, callback, qos_profile=ROS2Config.VIDEO_QOS
    ):
        self.create_subscription(msg_type, topic, callback, qos_profile)
        logger.info(f"Subscribed to {topic}")
