import base64
import logging
import time
from typing import Dict, Optional

import cv2
import numpy as np

# Delete if unused
# import roslibpy
from services.frame_recorder import FrameRecorder

logger = logging.getLogger(__name__)


class ROSCameraSubscriber:
    """Subscribes to ROS2 camera feed via rosbridge."""

    def __init__(
        self,
        topic: str,
        host: str = "localhost",
        port: int = 9090,
        callback=None,
        save_path: Optional[str] = None,
    ):
        self.topic = topic
        self.callback = callback
        self.recorder = None

        # Connect to rosbridge
        # self.client = roslibpy.Ros(host=host, port=port)
        self.client.run()
        logger.info(f"Connected to rosbridge at {host}:{port}")

        # Subscribe to image topic
        # self.subscriber = roslibpy.Topic(self.client, topic, "sensor_msgs/Image")
        self.subscriber.subscribe(self._image_callback)

        if save_path:
            self.recorder = FrameRecorder(save_path, "ros")

        logger.info(f"Subscribed to {topic}")

    def _image_callback(self, message: Dict) -> None:
        """Internal callback for ROS image messages."""
        try:
            cv_image, timestamp_ms = self._decode_ros_image(message)
            if cv_image is not None:
                # Save with timestamp if recorder enabled
                if self.recorder:
                    self.recorder.save_frame(cv_image, timestamp_ms)

                # Call user callback with timestamp
                if self.callback:
                    self.callback(cv_image, timestamp_ms)
        except Exception as e:
            logger.error(f"Error processing ROS image: {e}")

    def _decode_ros_image(self, message: Dict) -> tuple[Optional[np.ndarray], int]:
        """Decode ROS image message to OpenCV format with timestamp."""
        width = message["width"]
        height = message["height"]
        encoding = message["encoding"]
        data = message["data"]
        timestamp_ms = int(time.time_ns() / 1e6)

        if encoding not in ["rgb8"]:
            logger.warning(f"Unsupported encoding: {encoding}")
            return None, int(time.time_ns() / 1e6)

        # Decode base64 if necessary
        if isinstance(data, str):
            image_data = base64.b64decode(data)
        else:
            image_data = bytes(data)

        # Convert based on encoding
        image_array = np.frombuffer(image_data, dtype=np.uint8)
        image_array = image_array.reshape((height, width, 3))
        cv_image = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        return cv_image, timestamp_ms

    def cleanup(self) -> None:
        """Cleanup ROS connection."""
        self.subscriber.unsubscribe()
        self.client.terminate()
