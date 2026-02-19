"""
Dual Stream Feature Matcher
Matches features between Aria glasses and ROS2 camera streams using LightGlue.
"""

import logging
import pickle
import threading
import time
from multiprocessing.synchronize import Event
from queue import Queue
from threading import Lock, Thread
from typing import Dict, Optional

import numpy as np
import roslibpy
import torch
from lightglue import LightGlue, SuperPoint
from lightglue.utils import numpy_image_to_torch, rbd
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import UInt8MultiArray

from config import VIDEO_QOS, ROS2Topics, Settings
from services.ros import (
    ImageHelper,
    ROSPublisher,
    subscribe_realsense_color_feed,
)

# Configuration
torch.set_grad_enabled(False)
logger = logging.getLogger(__name__)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

_EXTRACTOR = SuperPoint(max_num_keypoints=2048).eval().to(Settings.DEVICE)
_MATCHER = LightGlue(features="superpoint").eval().to(Settings.DEVICE)


# ---------------------------------------------------------------------------
# Feature extraction & matching
# ---------------------------------------------------------------------------


class FeatureMatcher:
    """Extracts and matches keypoints between two images using LightGlue."""

    def __init__(self):
        self._extractor = _EXTRACTOR
        self._matcher = _MATCHER

    def match_frames(self, image0: np.ndarray, image1: np.ndarray) -> Dict:
        """
        Extract keypoints from both images and return matched pairs.

        Args:
            image0: First image (H x W x 3, uint8).
            image1: Second image (H x W x 3, uint8).

        Returns:
            Dict with keys: frame0, frame1, keypoints0, keypoints1, matches
        """
        feats0 = self._extractor.extract(
            numpy_image_to_torch(image0).to(Settings.DEVICE)
        )
        feats1 = self._extractor.extract(
            numpy_image_to_torch(image1).to(Settings.DEVICE)
        )
        matches01 = self._matcher({"image0": feats0, "image1": feats1})
        feats0, feats1, matches01 = [rbd(x) for x in [feats0, feats1, matches01]]

        return {
            "frame0": ImageHelper.compress_image(image0)[1],
            "frame1": ImageHelper.compress_image(image1)[1],
            "keypoints0": feats0["keypoints"].cpu().numpy(),
            "keypoints1": feats1["keypoints"].cpu().numpy(),
            "matches": matches01["matches"].cpu().numpy(),
        }


# ---------------------------------------------------------------------------
# Background matching worker
# ---------------------------------------------------------------------------


class MatchingWorker:
    """
    Runs feature matching on a dedicated thread.

    Keeps a queue of depth 1 so inference always operates on the
    most recently submitted frame pair, discarding stale submissions.
    """

    def __init__(self):
        self._matcher = FeatureMatcher()
        self._queue = Queue(maxsize=1)
        self._result_lock = Lock()
        self._result: Optional[Dict] = None
        self._active = True
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, frame0: np.ndarray, frame1: np.ndarray) -> bool:
        """
        Submit a frame pair for matching.

        If the worker is still busy (queue full), the submission is skipped
        and the caller waits for the next frame from the subscription.
        This ensures inference always starts with the freshest available
        frame at the moment the worker becomes free.

        Returns:
            True if submitted, False if skipped.
        """
        if not self._queue.empty():
            return False
        try:
            self._queue.put_nowait((frame0.copy(), frame1.copy()))
            return True
        except Exception as e:
            logger.error(f"Failed to submit frames: {e}")
            return False

    def stop(self) -> None:
        self._active = False

    def _loop(self) -> None:
        while self._active:
            if self._queue.empty():
                time.sleep(0.05)
                continue
            try:
                frame0, frame1 = self._queue.get()
                result = self._matcher.match_frames(frame0, frame1)
                with self._result_lock:
                    self._result = result
            except Exception as e:
                logger.error(f"Matching error: {e}", exc_info=True)

    def get_result(self) -> Optional[Dict]:
        with self._result_lock:
            result, self._result = self._result, None
            return result


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class FeatureMatchingPipeline:
    """
    Coordinates feature matching between Aria and ROS2 camera streams.

    Frame flow:
        ROS callbacks → raw frames (protected by _frame_lock)
            → MatchingWorker (background thread)
                → _publish_results() (main loop)
    """

    def __init__(self, quit_event: Event):
        self._quit_event = quit_event
        self._frame_lock = Lock()

        self._aria_frame: Optional[np.ndarray] = None
        self._ros_frame: Optional[np.ndarray] = None

        self._matching_worker = MatchingWorker()

        self._setup_ros()
        logger.debug("Feature matching pipeline initialised")

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ros(self) -> None:
        self._aria_camera_subscriber = Node("Aria_RGB_camera_subscriber")

        self._aria_camera_subscriber.create_subscription(
            CompressedImage,
            ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
            self._on_aria_frame,
            VIDEO_QOS,
        )
        subscribe_realsense_color_feed(self._aria_camera_subscriber, self._on_ros_frame)

        self._match_publisher = ROSPublisher(
            "match_publisher", UInt8MultiArray, ROS2Topics.FEATURE_MATCH_RESULTS.value
        )

        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._aria_camera_subscriber)

        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

    # ------------------------------------------------------------------
    # ROS callbacks
    # ------------------------------------------------------------------

    def _on_aria_frame(self, msg: CompressedImage) -> None:
        frame = ImageHelper.uncompress_image(image_bytes=msg.data)
        with self._frame_lock:
            self._aria_frame = frame
        self._trigger_matching()

    def _on_ros_frame(self, frame: np.ndarray) -> None:
        with self._frame_lock:
            self._ros_frame = frame
        self._trigger_matching()

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _trigger_matching(self) -> None:
        with self._frame_lock:
            if self._aria_frame is None or self._ros_frame is None:
                return
            self._matching_worker.submit(self._aria_frame, self._ros_frame)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def _publish_results(self, results: Dict) -> None:
        try:
            payload = pickle.dumps(results)
            msg = UInt8MultiArray()
            msg.data = payload
            self._match_publisher.publish(msg)
            logger.debug(f"Published match results ({len(payload) / 1024:.1f} KB)")

        except Exception as e:
            logger.error(f"Failed to publish match results: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        logger.info("Feature matching pipeline running")
        try:
            while not self._quit_event.is_set():
                result = self._matching_worker.get_result()
                if result:
                    self._publish_results(result)
                time.sleep(0.01)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        logger.info("Cleaning up...")
        self._matching_worker.stop()
        self._executor.shutdown()
        self._spin_thread.join(timeout=2.0)
        logger.info("Cleanup complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def feature_matching(aria_streaming_started: Event, quit_event: Event) -> None:
    FeatureMatchingPipeline(quit_event=quit_event).run()
