import logging

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Header

from config import ROS2Config

logger = logging.getLogger(__name__)


class ROSPublisher(Node):
    def __init__(
        self,
        node_name: str,
        msg_type: type,
        topic: str,
        qos_profile=ROS2Config.VIDEO_QOS,
    ):
        if not rclpy.ok():
            rclpy.init()
        super().__init__(node_name)
        self.publisher = self.create_publisher(msg_type, topic, qos_profile)
        logger.info(f"Publishing to {topic}")

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

    def publish_pose(self, pose_data) -> None:
        msg = PoseStamped()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "world"

        pos = pose_data["position"]
        msg.pose.position.x = float(pos[0])
        msg.pose.position.y = float(pos[1])
        msg.pose.position.z = float(pos[2])

        quat = pose_data["quaternion"]
        msg.pose.orientation.x = float(quat[0])
        msg.pose.orientation.y = float(quat[1])
        msg.pose.orientation.z = float(quat[2])
        msg.pose.orientation.w = float(quat[3])

        self.publisher.publish(msg)
