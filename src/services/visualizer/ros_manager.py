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
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import UInt8MultiArray

from config import ROS2Topics
from services.ros.ros_subscriber import ROSSubscriber

logger = logging.getLogger(__name__)


class ROSManager:
    """
    Owns all ROS2 subscriber nodes and the executor thread.

    Callbacks are injected at construction time so this class has
    no direct dependency on Visualizer internals.

    Usage:
        manager = ROSManager(
            on_raw_image=...,
            on_undistorted_image=...,
            on_gaze_position=...,
            on_mask_bundle=...,
        )
        manager.start()
        # ... run loop ...
        manager.stop()
    """

    def __init__(
        self,
        on_raw_image: Callable[[CompressedImage], None],
        on_undistorted_image: Callable[[CompressedImage], None],
        on_gaze_position: Callable[[Point], None],
        on_mask_bundle: Callable[[dict], None],
        on_feature_match: Callable[[dict], None],
    ):
        self._on_raw_image = on_raw_image
        self._on_undistorted_image = on_undistorted_image
        self._on_gaze_position = on_gaze_position
        self._on_mask_bundle = on_mask_bundle
        self._on_feature_match = on_feature_match

        self._executor: Optional[MultiThreadedExecutor] = None
        self._spin_thread: Optional[threading.Thread] = None

        self._rgb_subscriber: Optional[ROSSubscriber] = None
        self._undistorted_rgb_subscriber: Optional[ROSSubscriber] = None
        self._gaze_position_subscriber: Optional[ROSSubscriber] = None
        self._object_detection_inference_subscriber: Optional[ROSSubscriber] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise ROS2, create subscribers, and begin spinning."""
        if not rclpy.ok():
            rclpy.init()

        self._rgb_subscriber = ROSSubscriber("Aria_RGB_camera_subscriber")
        self._undistorted_rgb_subscriber = ROSSubscriber(
            "Aria_RGB_camera_undistorted_subscriber"
        )
        self._gaze_position_subscriber = ROSSubscriber("gaze_position_subscriber")
        self._object_detection_inference_subscriber = ROSSubscriber(
            "object_detection_inference_subscriber"
        )
        self._feature_matching_subscriber = ROSSubscriber("match_publisher")

        self._rgb_subscriber.subscribe(
            CompressedImage,
            ROS2Topics.RGB_CAMERA_RAW.value,
            self._on_raw_image,
        )
        self._undistorted_rgb_subscriber.subscribe(
            CompressedImage,
            ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
            self._on_undistorted_image,
        )
        self._gaze_position_subscriber.subscribe(
            Point,
            ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value,
            self._on_gaze_position,
        )
        self._object_detection_inference_subscriber.subscribe(
            UInt8MultiArray,
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS.value,
            lambda msg: self._unpickle_and_forward(msg, self._on_mask_bundle),
        )
        self._feature_matching_subscriber.subscribe(
            UInt8MultiArray,
            ROS2Topics.FEATURE_MATCH_RESULTS.value,
            lambda msg: self._unpickle_and_forward(msg, self._on_feature_match),
        )

        self._executor = MultiThreadedExecutor()
        for node in (
            self._rgb_subscriber,
            self._undistorted_rgb_subscriber,
            self._gaze_position_subscriber,
            self._object_detection_inference_subscriber,
            self._feature_matching_subscriber,
        ):
            self._executor.add_node(node)

        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()
        logger.info("ROS2 subscribers started")

    def stop(self) -> None:
        """Destroy subscriber nodes gracefully."""
        for node in (
            self._rgb_subscriber,
            self._undistorted_rgb_subscriber,
            self._gaze_position_subscriber,
            self._object_detection_inference_subscriber,
        ):
            if node is None:
                continue
            try:
                node.destroy_node()
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
