import logging

import numpy as np
from sensor_msgs.msg import Image

from config import ROS2Config

from .ros_subscriber import ROSSubscriber

logger = logging.getLogger(__name__)


class RealmanCameraSubscriber(ROSSubscriber):
    def __init__(self, node_name: str):
        super().__init__(node_name)

    def _imgmsg_to_cv2(self, msg: Image):
        return np.frombuffer(msg.data, dtype=np.uint8).reshape(
            msg.height, msg.width, -1
        )

    def _depth_imgmsg_to_cv2(self, msg: Image):
        return np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)

    def subscribe_color_feed(self, callback, qos_profile=ROS2Config.VIDEO_QOS):
        topic = "/camera/camera/color/image_raw"

        def _callback(msg: Image):
            frame = self._imgmsg_to_cv2(msg)
            callback(frame)

        self.create_subscription(
            msg_type=Image, topic=topic, callback=_callback, qos_profile=qos_profile
        )
        logger.info(f"Subscribed to {topic}")

    def subscribe_depth_feed(self, callback, qos_profile=ROS2Config.VIDEO_QOS):
        topic = "/camera/camera/depth/image_raw"

        def _callback(msg: Image):
            frame = self._depth_imgmsg_to_cv2(msg)
            callback(frame)

        self.create_subscription(
            msg_type=Image, topic=topic, callback=_callback, qos_profile=qos_profile
        )
        logger.info(f"Subscribed to {topic}")
