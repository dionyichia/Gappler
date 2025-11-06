# services/ros_service.py
import rospy
from std_msgs.msg import String
from sensor_msgs.msg import Image as ImageROS
from cv_bridge import CvBridge
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ROSService:
    """Service for ROS communication"""

    def __init__(self, config):
        self.config = config
        self.bridge = CvBridge()
        self.action_publisher = rospy.Publisher(
            config.action_topic, String, queue_size=1
        )

        logger.info(f"ROSService initialized. Publishing to {config.action_topic}")

    def get_image_from_topic(
        self, topic_name: str, timeout: float = 10.0
    ) -> np.ndarray:
        """
        Get image from ROS topic

        Args:
            topic_name: ROS topic to subscribe to
            timeout: Maximum wait time in seconds

        Returns:
            Image as numpy array (BGR format)
        """
        try:
            ros_image = rospy.wait_for_message(topic_name, ImageROS, timeout=timeout)
            image = self.bridge.imgmsg_to_cv2(ros_image, desired_encoding="bgr8")
            logger.info(f"Received image from {topic_name}")
            return image
        except rospy.ROSException as e:
            logger.error(f"Failed to get image from {topic_name}: {e}")
            raise

    def wait_for_gpt_request(self, timeout: float = None) -> dict:
        """
        Wait for GPT request message from ROS

        Args:
            timeout: Maximum wait time in seconds (None = infinite)

        Returns:
            Parsed JSON dictionary
        """
        logger.info(f"Waiting for message on {self.config.modified_response_topic}...")

        message = rospy.wait_for_message(
            self.config.modified_response_topic, String, timeout=timeout
        )

        # Parse message
        import json

        message_str = message.data.replace("'", '"')
        data = json.loads(message_str)

        logger.info("Received GPT request")
        return data

    def publish_action(self, action_data: dict):
        """
        Publish action plan to ROS topic

        Args:
            action_data: Action plan dictionary or list
        """
        import json

        message = json.dumps(action_data)
        self.action_publisher.publish(message)
        logger.info(f"Published action: {message}")
