import logging

import numpy as np
from rclpy.node import Node
from sensor_msgs.msg import Image

from config import VIDEO_QOS

logger = logging.getLogger(__name__)


def _imgmsg_to_cv2(msg: Image):
    return np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)


def _depth_imgmsg_to_cv2(msg: Image):
    return np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)


def subscribe_realsense_color_feed(node: Node, callback, qos_profile=VIDEO_QOS):
    topic = "/camera/camera/color/image_raw"

    def _callback(msg: Image):
        frame = _imgmsg_to_cv2(msg)
        callback(frame)

    node.create_subscription(
        msg_type=Image, topic=topic, callback=_callback, qos_profile=qos_profile
    )
    logger.debug(f"Subscribed to {topic}")


def subscribe_realsense_depth_feed(node: Node, callback, qos_profile=VIDEO_QOS):
    topic = "/camera/camera/depth/image_raw"

    def _callback(msg: Image):
        frame = _depth_imgmsg_to_cv2(msg)
        callback(frame)

    node.create_subscription(
        msg_type=Image, topic=topic, callback=_callback, qos_profile=qos_profile
    )
    logger.debug(f"Subscribed to {topic}")
