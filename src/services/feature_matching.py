"""
Dual Stream Feature Matcher
Matches features between Aria glasses and ROS2 camera streams using LightGlue.
"""

import logging
import pickle
import threading
import time
from dataclasses import dataclass, field
from multiprocessing.synchronize import Event
from queue import Queue
from threading import Lock, Thread
from typing import Dict, Optional, Tuple

import numpy as np
import torch
from lightglue import LightGlue, SuperPoint
from lightglue.utils import numpy_image_to_torch, rbd
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import UInt8MultiArray

from config import ROS2Topics, Settings
from services.ros import RealmanCameraSubscriber, ROSSubscriber
from services.ros.image_helper import ImageHelper
from services.ros.ros_publisher import ROSPublisher
from services.visualizer.renderers.object_mask_visualizer import ObjectMaskVisualizer

# Configuration
torch.set_grad_enabled(False)
logger = logging.getLogger(__name__)

_EXTRACTOR = SuperPoint(max_num_keypoints=2048).eval().to(Settings.DEVICE)
_MATCHER = LightGlue(features="superpoint").eval().to(Settings.DEVICE)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class FrameBundle:
    """Paired frames and optional inference results from the object detection pipeline."""

    aria_frame: np.ndarray
    ros_frame: np.ndarray
    aria_inference: Optional[dict] = field(default=None)
    ros_inference: Optional[dict] = field(default=None)


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

    def __init__(self, matcher: FeatureMatcher):
        self._matcher = matcher
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

    def consume_result(self) -> Optional[Dict]:
        """Return and clear the latest result to prevent duplicate publishing."""
        with self._result_lock:
            result, self._result = self._result, None
            return result

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


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class FeatureMatchingPipeline:
    """
    Coordinates feature matching between Aria and ROS2 camera streams.

    Frame flow:
        ROS callbacks → raw frames / bundle (protected by _frame_lock)
            → MatchingWorker (background thread)
                → _publish_results() (main loop)
    """

    def __init__(self, quit_event: Event):
        self._quit_event = quit_event
        self._matching_enabled = True
        self._frame_lock = Lock()

        self._aria_frame: Optional[np.ndarray] = None
        self._ros_frame: Optional[np.ndarray] = None
        self._bundle: Optional[FrameBundle] = None

        self._matcher = FeatureMatcher()
        self._matching_worker = MatchingWorker(self._matcher)

        self._setup_ros()
        logger.info("Feature Matching Pipeline initialised")

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ros(self) -> None:
        self._aria_camera_subscriber = ROSSubscriber("Aria_RGB_camera_subscriber")
        self._ros_camera_subscriber = RealmanCameraSubscriber(
            "realman_camera_subscriber"
        )
        self._mask_subscriber = ROSSubscriber("object_detection_inference_subscriber")

        self._aria_camera_subscriber.subscribe(
            CompressedImage,
            ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
            self._on_aria_frame,
        )
        self._ros_camera_subscriber.subscribe_color_feed(self._on_ros_frame)
        self._mask_subscriber.subscribe(
            UInt8MultiArray,
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS.value,
            self._on_mask_bundle,
        )

        self._match_publisher = ROSPublisher(
            "match_publisher", UInt8MultiArray, ROS2Topics.FEATURE_MATCH_RESULTS.value
        )

        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._aria_camera_subscriber)
        self._executor.add_node(self._ros_camera_subscriber)
        self._executor.add_node(self._mask_subscriber)

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

    def _on_mask_bundle(self, msg: UInt8MultiArray) -> None:
        try:
            bundle = pickle.loads(bytes(msg.data))
            aria_bundle = bundle.get("aria", {})
            ros_bundle = bundle.get("ros", {})

            aria_image = ImageHelper.uncompress_image(aria_bundle.get("image", b""))
            ros_image = ImageHelper.uncompress_image(ros_bundle.get("image", b""))

            if aria_image is None or ros_image is None:
                logger.debug("Mask bundle missing image(s), ignoring bundle")
                return

            with self._frame_lock:
                self._bundle = FrameBundle(
                    aria_frame=aria_image,
                    ros_frame=ros_image,
                    aria_inference=aria_bundle.get("inference_state"),
                    ros_inference=ros_bundle.get("inference_state"),
                )
            self._trigger_matching()

        except Exception as e:
            logger.error(f"Failed to deserialize mask bundle: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _get_best_frame_pair(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Return the best available frame pair.
        Bundle frames are preferred (temporally synced); raw feeds are the fallback.
        Must be called with _frame_lock held.
        """
        if self._bundle is not None:
            logger.debug("Using bundle frames")
            return self._bundle.aria_frame, self._bundle.ros_frame

        if self._aria_frame is not None and self._ros_frame is not None:
            logger.debug("Using raw camera frames")
            return self._aria_frame, self._ros_frame

        return None

    def _trigger_matching(self) -> None:
        if not self._matching_enabled:
            return
        with self._frame_lock:
            pair = self._get_best_frame_pair()
            if pair is not None:
                self._matching_worker.submit(*pair)

    def toggle_matching(self) -> None:
        self._matching_enabled = not self._matching_enabled
        logger.info(f"Matching {'enabled' if self._matching_enabled else 'disabled'}")

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def _annotate_frame(self, compressed: bytes, inference: Optional[dict]) -> bytes:
        """Overlay masks onto a compressed frame if inference results are available."""
        if inference is None:
            return compressed
        image = ImageHelper.uncompress_image(compressed)
        annotated = ObjectMaskVisualizer.plot_results(img=image, results=inference)
        return ImageHelper.compress_image(annotated)[1]

    def _publish_results(self, results: Dict) -> None:
        try:
            with self._frame_lock:
                bundle = self._bundle

            if bundle is not None:
                results["frame0"] = self._annotate_frame(
                    results["frame0"], bundle.aria_inference
                )
                results["frame1"] = self._annotate_frame(
                    results["frame1"], bundle.ros_inference
                )

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
        logger.info("Feature Matching Pipeline running")
        try:
            while not self._quit_event.is_set():
                results = self._matching_worker.consume_result()
                if results is not None:
                    self._publish_results(results)
                else:
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
