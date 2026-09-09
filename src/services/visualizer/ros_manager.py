"""
ROS2 subscriber manager: sets up and spins all topic subscribers for the Visualizer.
"""

import logging
import pickle
import threading
from typing import Callable, Optional

import rclpy
from geometry_msgs.msg import Point
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import UInt8MultiArray

from config import VIDEO_QOS, ROS2Topics

logger = logging.getLogger(__name__)


class ROSManager:
    """
    Owns all ROS2 subscriber nodes and the executor thread.

    Callbacks are injected at construction time so this class has
    no direct dependency on Visualizer internals.
    """

    def __init__(
        self,
        on_raw_image: Callable[[CompressedImage], None],
        on_undistorted_image: Callable[[CompressedImage], None],
        on_gaze_position: Callable[[Point], None],
        on_et_raw_image: Callable[[CompressedImage], None],
        on_aria_mask_bundle: Callable[[dict], None],
        on_ros_mask_bundle: Callable[[dict], None],
        on_feature_match: Callable[[dict], None],
        on_combined_bundle: Callable[[dict], None],
    ):
        self._on_raw_image = on_raw_image
        self._on_undistorted_image = on_undistorted_image
        self._on_gaze_position = on_gaze_position
        self._on_et_raw_image = on_et_raw_image
        self._on_aria_mask_bundle = on_aria_mask_bundle
        self._on_ros_mask_bundle = on_ros_mask_bundle
        self._on_feature_match = on_feature_match
        self._on_combined_bundle = on_combined_bundle

        self._subscriber: Optional[Node] = None
        self._executor: Optional[MultiThreadedExecutor] = None
        self._spin_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise ROS2, create subscribers, and begin spinning."""
        if not rclpy.ok():
            rclpy.init()

        self._subscriber = Node("visualizer_subscriber")

        self._subscriber.create_subscription(
            CompressedImage,
            ROS2Topics.RGB_CAMERA_RAW.value,
            self._on_raw_image,
            VIDEO_QOS,
        )
        self._subscriber.create_subscription(
            CompressedImage,
            ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
            self._on_undistorted_image,
            VIDEO_QOS,
        )
        self._subscriber.create_subscription(
            Point,
            ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value,
            self._on_gaze_position,
            VIDEO_QOS,
        )
        self._subscriber.create_subscription(
            CompressedImage,
            ROS2Topics.EYE_TRACKING_RAW.value,
            self._on_et_raw_image,
            VIDEO_QOS,
        )
        self._subscriber.create_subscription(
            UInt8MultiArray,
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS.value,
            lambda msg: self._unpickle_and_forward(msg, self._on_aria_mask_bundle),
            VIDEO_QOS,
        )
        self._subscriber.create_subscription(
            UInt8MultiArray,
            ROS2Topics.ROS_CAMERA_WITH_OBJECT_MASKS.value,
            lambda msg: self._unpickle_and_forward(msg, self._on_ros_mask_bundle),
            VIDEO_QOS,
        )
        self._subscriber.create_subscription(
            UInt8MultiArray,
            ROS2Topics.FEATURE_MATCH_RESULTS.value,
            lambda msg: self._unpickle_and_forward(msg, self._on_feature_match),
            VIDEO_QOS,
        )
        self._subscriber.create_subscription(
            UInt8MultiArray,
            ROS2Topics.COMBINED_VISUALIZATION.value,
            lambda msg: self._unpickle_and_forward(msg, self._on_combined_bundle),
            VIDEO_QOS,
        )

        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._subscriber)

        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()
        logger.info("ROS2 subscribers started")

    def stop(self) -> None:
        """Destroy subscriber nodes gracefully."""
        if self._subscriber is not None:
            try:
                self._subscriber.destroy_node()
            except Exception as e:
                logger.warning(f"Error destroying node: {e}")
        logger.info("ROS2 subscribers stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unpickle_and_forward(
        msg: UInt8MultiArray,
        callback: Callable[[dict], None],
    ) -> None:
        """Deserialize a pickled UInt8MultiArray message and forward to callback."""
        try:
            bundle = pickle.loads(bytes(msg.data))
        except Exception as e:
            logger.error(f"Failed to deserialize message: {e}")
            return
        callback(bundle)
