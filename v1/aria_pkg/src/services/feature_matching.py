"""
Dual Stream Feature Matcher with integrated visualization
Matches features between Aria glasses and ROS2 camera streams using LightGlue.
"""

import logging
import time
from pathlib import Path
from queue import Queue
from threading import Lock, Thread
from typing import Optional, Dict
import base64

import cv2
import numpy as np
import roslibpy
import torch

import aria.sdk as aria

from models.LightGlue.lightglue import LightGlue, SuperPoint
from models.LightGlue.lightglue.utils import numpy_image_to_torch, rbd

import config
import services.eye_tracking
from aria_device.aria_stream_client import AriaStreamClient
from aria_device.streaming_client_observer import ImageObserver
from utils.keyboard import quit_keypress

# Configuration
torch.set_grad_enabled(False)
logger = logging.getLogger(__name__)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Model initialization
EXTRACTOR = SuperPoint(max_num_keypoints=2048).eval().to(DEVICE)
MATCHER = LightGlue(features="superpoint").eval().to(DEVICE)


def draw_matches_opencv(image0, image1, kpts0, kpts1, matches, max_matches=100):
    """
    Draw feature matches on two images using OpenCV.
    Args:
        image0, image1: Input images (numpy arrays)
        kpts0, kpts1: Keypoints (torch tensors or numpy arrays)
        matches: Match indices (torch tensor or numpy array)
        max_matches: Maximum number of matches to draw for clarity
    Returns:
        Combined image with matches drawn
    """
    # Convert tensors to numpy if needed
    if isinstance(kpts0, torch.Tensor):
        kpts0 = kpts0.cpu().numpy()
    if isinstance(kpts1, torch.Tensor):
        kpts1 = kpts1.cpu().numpy()
    if isinstance(matches, torch.Tensor):
        matches = matches.cpu().numpy()

    # Get matched keypoints
    if len(matches) > 0:
        matched_kpts0 = kpts0[matches[:, 0]].copy()
        matched_kpts1 = kpts1[matches[:, 1]].copy()

        # Limit number of matches for visual clarity
        if len(matched_kpts0) > max_matches:
            indices = np.random.choice(len(matched_kpts0), max_matches, replace=False)
            matched_kpts0 = matched_kpts0[indices]
            matched_kpts1 = matched_kpts1[indices]
    else:
        matched_kpts0 = np.array([])
        matched_kpts1 = np.array([])

    # Ensure images are same height and scale keypoints accordingly
    h0, w0 = image0.shape[:2]
    h1, w1 = image1.shape[:2]

    scale0 = 1.0
    scale1 = 1.0

    if h0 != h1:
        target_h = max(h0, h1)
        if h0 < target_h:
            scale0 = target_h / h0
            image0 = cv2.resize(image0, (int(w0 * scale0), target_h))
            if len(matched_kpts0) > 0:
                matched_kpts0 *= scale0
        if h1 < target_h:
            scale1 = target_h / h1
            image1 = cv2.resize(image1, (int(w1 * scale1), target_h))
            if len(matched_kpts1) > 0:
                matched_kpts1 *= scale1

    # Create side-by-side image
    h, w0 = image0.shape[:2]
    _, w1 = image1.shape[:2]
    combined = np.zeros((h, w0 + w1, 3), dtype=np.uint8)
    combined[:, :w0] = image0
    combined[:, w0:] = image1

    # Draw matches
    if len(matched_kpts0) > 0:
        for i in range(len(matched_kpts0)):
            pt0 = tuple(matched_kpts0[i].astype(int))
            pt1 = tuple((matched_kpts1[i] + [w0, 0]).astype(int))

            # Generate color based on position (gradient effect)
            color_val = i / max(len(matched_kpts0) - 1, 1)
            color = (
                int(255 * (1 - color_val)),  # B
                int(255 * color_val * 0.5),  # G
                int(255 * color_val),  # R
            )

            # Draw line
            cv2.line(combined, pt0, pt1, color, 1, cv2.LINE_AA)
            # Draw keypoints
            cv2.circle(combined, pt0, 3, color, -1, cv2.LINE_AA)
            cv2.circle(combined, pt1, 3, color, -1, cv2.LINE_AA)

    return combined


class FeatureMatcher:
    """Handles feature extraction and matching between two images using LightGlue."""

    def __init__(self):
        self.extractor = EXTRACTOR
        self.matcher = MATCHER
        logger.info("Feature matcher initialized")

    def match_frames(
        self, image0: np.ndarray, image1: np.ndarray
    ) -> Dict[str, torch.Tensor]:
        """
        Match features between two frames.

        Args:
            image0: First image (numpy array)
            image1: Second image (numpy array)

        Returns:
            Dictionary containing keypoints and matches
        """
        # Extract features
        feats0 = self.extractor.extract(numpy_image_to_torch(image0).to(DEVICE))
        feats1 = self.extractor.extract(numpy_image_to_torch(image1).to(DEVICE))

        # Match features
        matches01 = self.matcher({"image0": feats0, "image1": feats1})

        # Remove batch dimension
        feats0, feats1, matches01 = [rbd(x) for x in [feats0, feats1, matches01]]

        return {
            "keypoints0": feats0["keypoints"],
            "keypoints1": feats1["keypoints"],
            "matches": matches01["matches"],
            "stop_layer": matches01["stop"],
            "prune0": matches01["prune0"],
            "prune1": matches01["prune1"],
        }


class FrameBuffer:
    """Thread-safe frame buffer with timestamp tracking."""

    def __init__(self, name: str):
        self.name = name
        self._lock = Lock()
        self._frame: Optional[np.ndarray] = None
        self._frame_count = 0
        self._fps = 0.0
        self._last_fps_time = time.time()

    def update(self, frame: np.ndarray) -> None:
        """Update buffer with new frame."""
        with self._lock:
            self._frame = frame.copy()
            self._frame_count += 1

    def get(self) -> Optional[np.ndarray]:
        """Get current frame."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def is_ready(self) -> bool:
        """Check if buffer has a frame."""
        with self._lock:
            return self._frame is not None

    def update_fps(self) -> None:
        """Update FPS calculation."""
        current_time = time.time()
        with self._lock:
            elapsed = current_time - self._last_fps_time
            if elapsed >= 1.0:
                self._fps = self._frame_count / elapsed
                self._frame_count = 0
                self._last_fps_time = current_time

    @property
    def fps(self) -> float:
        """Get current FPS."""
        with self._lock:
            return self._fps

    def reset_stats(self) -> None:
        """Reset frame counter and FPS."""
        with self._lock:
            self._frame_count = 0
            self._last_fps_time = time.time()
            self._fps = 0.0


class ROSCameraSubscriber:
    """Subscribes to ROS2 camera feed via rosbridge."""

    def __init__(
        self, topic: str, host: str = "localhost", port: int = 9090, callback=None
    ):
        self.topic = topic
        self.callback = callback

        # Connect to rosbridge
        self.client = roslibpy.Ros(host=host, port=port)
        self.client.run()
        logger.info(f"Connected to rosbridge at {host}:{port}")

        # Subscribe to image topic
        self.subscriber = roslibpy.Topic(self.client, topic, "sensor_msgs/Image")
        self.subscriber.subscribe(self._image_callback)
        logger.info(f"Subscribed to {topic}")

    def _image_callback(self, message: Dict) -> None:
        """Internal callback for ROS image messages."""
        try:
            cv_image = self._decode_ros_image(message)
            if cv_image is not None and self.callback:
                self.callback(cv_image)
        except Exception as e:
            logger.error(f"Error processing ROS image: {e}")

    def _decode_ros_image(self, message: Dict) -> Optional[np.ndarray]:
        """Decode ROS image message to OpenCV format."""
        width = message["width"]
        height = message["height"]
        encoding = message["encoding"]
        data = message["data"]

        # Decode base64 if necessary
        if isinstance(data, str):
            image_data = base64.b64decode(data)
        else:
            image_data = bytes(data)

        # Convert based on encoding
        if encoding == "rgb8":
            image_array = np.frombuffer(image_data, dtype=np.uint8)
            image_array = image_array.reshape((height, width, 3))
            return cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        elif encoding == "bgr8":
            image_array = np.frombuffer(image_data, dtype=np.uint8)
            return image_array.reshape((height, width, 3))
        else:
            logger.warning(f"Unsupported encoding: {encoding}")
            return None

    def cleanup(self) -> None:
        """Cleanup ROS connection."""
        self.subscriber.unsubscribe()
        self.client.terminate()


class MatchingWorker:
    """Background worker thread for feature matching."""

    def __init__(self, matcher: FeatureMatcher):
        self.matcher = matcher
        self._queue = Queue(maxsize=1)
        self._result_lock = Lock()
        self._result: Optional[Dict] = None
        self._active = True

        # Start worker thread
        self._thread = Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def submit(self, frame0: np.ndarray, frame1: np.ndarray) -> bool:
        """
        Submit frames for matching.

        Returns:
            True if submitted, False if queue is full
        """
        if self._queue.empty():
            try:
                self._queue.put_nowait((frame0.copy(), frame1.copy()))
                return True
            except:
                return False
        return False

    def get_result(self) -> Optional[Dict]:
        """Get latest matching result."""
        with self._result_lock:
            return self._result

    def _worker_loop(self) -> None:
        """Main worker loop."""
        while self._active:
            if not self._queue.empty():
                try:
                    frame0, frame1 = self._queue.get()
                    result = self.matcher.match_frames(frame0, frame1)

                    with self._result_lock:
                        self._result = result
                except Exception as e:
                    logger.error(f"Matching error: {e}", exc_info=True)
            else:
                time.sleep(0.01)

    def stop(self) -> None:
        """Stop worker thread."""
        self._active = False


class DualStreamMatcher:
    """Main coordinator for dual stream feature matching."""

    def __init__(
        self,
        ros_topic: str = "/camera/color/image_raw",
        ros_host: str = "localhost",
        ros_port: int = 9090,
    ):
        # Components
        self.matcher = FeatureMatcher()
        self.aria_buffer = FrameBuffer("Aria")
        self.ros_buffer = FrameBuffer("ROS")
        self.matching_worker = MatchingWorker(self.matcher)

        # ROS subscriber
        self.ros_subscriber = ROSCameraSubscriber(
            topic=ros_topic, host=ros_host, port=ros_port, callback=self._on_ros_frame
        )

        # State
        self.matching_enabled = True
        self.show_matches = True  # Toggle for match visualization

        logger.info("Dual stream matcher initialized")

    def _on_ros_frame(self, frame: np.ndarray) -> None:
        """Callback for ROS frames."""
        self.ros_buffer.update(frame)
        self._trigger_matching()

    def on_aria_frame(self, frame: np.ndarray) -> None:
        """Callback for Aria frames."""
        # Rotate and convert Aria frame
        rotated = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        bgr_frame = cv2.cvtColor(rotated, cv2.COLOR_RGB2BGR)

        self.aria_buffer.update(bgr_frame)
        self._trigger_matching()

    def _trigger_matching(self) -> None:
        """Trigger matching if both frames are available."""
        if not self.matching_enabled:
            return

        if self.aria_buffer.is_ready() and self.ros_buffer.is_ready():
            aria_frame = self.aria_buffer.get()
            ros_frame = self.ros_buffer.get()

            if aria_frame is not None and ros_frame is not None:
                self.matching_worker.submit(aria_frame, ros_frame)

    def create_visualization(self) -> np.ndarray:
        """Create visualization with or without matches."""
        aria_frame = self.aria_buffer.get()
        ros_frame = self.ros_buffer.get()

        # Check if frames available
        if aria_frame is None or ros_frame is None:
            return self._create_placeholder()

        # Get match result
        match_result = self.matching_worker.get_result()

        # Update FPS
        self.aria_buffer.update_fps()
        self.ros_buffer.update_fps()

        if self.show_matches and match_result is not None:
            # Create match visualization
            visualization = draw_matches_opencv(
                aria_frame,
                ros_frame,
                match_result["keypoints0"],
                match_result["keypoints1"],
                match_result["matches"],
                max_matches=50,
            )

            # Add info overlay
            num_matches = len(match_result["matches"])
            info_text = [
                f"Aria: {self.aria_buffer.fps:.1f} FPS",
                f"ROS: {self.ros_buffer.fps:.1f} FPS",
                f"Matches: {num_matches}",
                f"Layer: {match_result['stop_layer']}",
            ]

            y_offset = 30
            for text in info_text:
                cv2.putText(
                    visualization,
                    text,
                    (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                y_offset += 30

            return visualization
        else:
            # Simple side-by-side view
            target_height = 480
            aria_resized = self._resize_frame(aria_frame, target_height)
            ros_resized = self._resize_frame(ros_frame, target_height)

            # Add labels
            self._add_label(aria_resized, f"Aria ({self.aria_buffer.fps:.1f} FPS)")
            self._add_label(ros_resized, f"ROS ({self.ros_buffer.fps:.1f} FPS)")

            # Add match count if available
            if match_result:
                num_matches = len(match_result["matches"])
                cv2.putText(
                    aria_resized,
                    f"Matches: {num_matches}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 0),
                    2,
                )

            return np.hstack([aria_resized, ros_resized])

    def _create_placeholder(self) -> np.ndarray:
        """Create placeholder image when frames not available."""
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            placeholder,
            "Waiting for frames...",
            (150, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )
        return placeholder

    def _resize_frame(self, frame: np.ndarray, target_height: int) -> np.ndarray:
        """Resize frame to target height maintaining aspect ratio."""
        h, w = frame.shape[:2]
        scale = target_height / h
        return cv2.resize(frame, (int(w * scale), target_height))

    def _add_label(self, frame: np.ndarray, text: str) -> None:
        """Add label text to frame."""
        cv2.putText(
            frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
        )

    def toggle_matching(self) -> None:
        """Toggle matching on/off."""
        self.matching_enabled = not self.matching_enabled
        status = "enabled" if self.matching_enabled else "disabled"
        logger.info(f"Matching {status}")

    def toggle_match_visualization(self) -> None:
        """Toggle match line visualization."""
        self.show_matches = not self.show_matches
        status = "enabled" if self.show_matches else "disabled"
        logger.info(f"Match visualization {status}")

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.aria_buffer.reset_stats()
        self.ros_buffer.reset_stats()
        logger.info("Statistics reset")

    def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up...")
        self.matching_worker.stop()
        self.ros_subscriber.cleanup()
        cv2.destroyAllWindows()
        logger.info("Cleanup complete")


def dual_stream_matcher(project_root: Path) -> None:
    """Main execution function."""
    logger.info("\n=== Dual Stream Feature Matcher ===")
    logger.info("Controls:")
    logger.info("  'q' - Quit")
    logger.info("  'm' - Toggle matching on/off")
    logger.info("  'v' - Toggle match visualization")
    logger.info("  's' - Save current frame")
    logger.info("  'r' - Reset statistics")
    logger.info("=" * 30 + "\n")

    # Initialize matcher
    matcher = DualStreamMatcher(
        ros_topic="/camera/color/image_raw", ros_host="localhost", ros_port=9090
    )

    # Initialize eye tracking
    save_path = project_root / "output"
    system = services.eye_tracking.initialize_eye_tracking(config.DEVICE)

    # Create window
    cv2.namedWindow("Aria + ROS2 Camera Matching", cv2.WINDOW_NORMAL)

    try:
        with AriaStreamClient() as aria_stream_client:
            # Subscribe to Aria RGB stream
            data_channels = [aria.StreamingDataType.Rgb]
            observer: ImageObserver = aria_stream_client.subscribe(
                data_channels,
                ImageObserver(
                    system.rgb_camera_calibration,
                    system.rgb_linear_camera_calibration,
                    str(save_path),
                    config.ImageStreamProcessorConfig().CAMERA_ID_MAP,
                ),
                message_queue_size=1,
            )
            logger.info("Aria streaming started")

            # Main loop
            while not quit_keypress():
                try:
                    # Get Aria frame
                    aria_frame = observer.get_undistorted_rgb_image()
                    if aria_frame is not None:
                        matcher.on_aria_frame(aria_frame)

                    # Create and show visualization
                    display = matcher.create_visualization()
                    cv2.imshow("Aria + ROS2 Camera Matching", display)

                    # Handle key presses
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
                    elif key == ord("m"):
                        matcher.toggle_matching()
                    elif key == ord("v"):
                        matcher.toggle_match_visualization()
                    elif key == ord("s"):
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        filename = f"dual_stream_match_{timestamp}.png"
                        cv2.imwrite(filename, display)
                        logger.info(f"Saved frame to {filename}")
                    elif key == ord("r"):
                        matcher.reset_stats()

                    # Small delay to prevent CPU spinning
                    time.sleep(0.5)

                except KeyError as e:
                    logger.debug(f"Frame not yet available: {e}")
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error during visualization: {e}", exc_info=True)
                    break

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        matcher.cleanup()
