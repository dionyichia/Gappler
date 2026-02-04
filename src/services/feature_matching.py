"""
Dual Stream Feature Matcher with integrated visualization and timestamp recording
Matches features between Aria glasses and ROS2 camera streams using LightGlue.
"""

import csv
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Lock, Thread
from typing import Dict, Optional

import cv2
import numpy as np
import torch

import config
from models.LightGlue.lightglue import LightGlue, SuperPoint
from models.LightGlue.lightglue.utils import numpy_image_to_torch, rbd
from services.frame_recorder import FrameRecorder
from services.ros_camera_subscriber import ROSCameraSubscriber
from utils.keyboard import quit_keypress

# Configuration
torch.set_grad_enabled(False)
logger = logging.getLogger(__name__)

# Model initialization
EXTRACTOR = SuperPoint(max_num_keypoints=2048).eval().to(config.Settings.DEVICE)
MATCHER = LightGlue(features="superpoint").eval().to(config.Settings.DEVICE)


@dataclass
class FrameData:
    """Container for frame with metadata"""

    frame: np.ndarray
    timestamp_ms: int
    source: str  # 'ros' or 'aria'


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
        feats0 = self.extractor.extract(
            numpy_image_to_torch(image0).to(config.Settings.DEVICE)
        )
        feats1 = self.extractor.extract(
            numpy_image_to_torch(image1).to(config.Settings.DEVICE)
        )

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

    def __init__(self, name: str, recorder: Optional[FrameRecorder] = None):
        self.name = name
        self.recorder = recorder
        self._lock = Lock()
        self._frame: Optional[np.ndarray] = None
        self._timestamp_ms: Optional[int] = None
        self._frame_count = 0
        self._fps = 0.0
        self._last_fps_time = time.time()

    def update(self, frame: np.ndarray, timestamp_ms: int) -> None:
        """Update buffer with new frame and timestamp."""
        with self._lock:
            self._frame = frame.copy()
            self._timestamp_ms = timestamp_ms
            self._frame_count += 1

            # Save if recorder is enabled
            if self.recorder:
                self.recorder.save_frame(frame, timestamp_ms)

    def get(self) -> Optional[np.ndarray]:
        """Get current frame."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def get_with_timestamp(self) -> Optional[FrameData]:
        """Get current frame with timestamp."""
        with self._lock:
            if self._frame is None:
                return None
            return FrameData(
                frame=self._frame.copy(),
                timestamp_ms=self._timestamp_ms,
                source=self.name,
            )

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


class MatchingWorker:
    """Background worker thread for feature matching."""

    def __init__(self, matcher: FeatureMatcher):
        self.matcher = matcher
        self._queue = Queue(maxsize=1)
        self._result_lock = Lock()
        self._result: Optional[Dict] = None
        self._result_metadata: Optional[Dict] = None
        self._active = True

        # Start worker thread
        self._thread = Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def submit(
        self, frame0: np.ndarray, frame1: np.ndarray, timestamp0: int, timestamp1: int
    ) -> bool:
        """
        Submit frames for matching with timestamps.

        Returns:
            True if submitted, False if queue is full
        """
        if self._queue.empty():
            try:
                self._queue.put_nowait(
                    (frame0.copy(), frame1.copy(), timestamp0, timestamp1)
                )
                return True
            except:
                return False
        return False

    def get_result(self) -> tuple[Optional[Dict], Optional[Dict]]:
        """Get latest matching result with metadata."""
        with self._result_lock:
            return self._result, self._result_metadata

    def _worker_loop(self) -> None:
        """Main worker loop."""
        while self._active:
            if not self._queue.empty():
                try:
                    frame0, frame1, ts0, ts1 = self._queue.get()
                    result = self.matcher.match_frames(frame0, frame1)

                    metadata = {
                        "timestamp0": ts0,
                        "timestamp1": ts1,
                        "time_diff_ms": abs(ts1 - ts0),
                    }

                    with self._result_lock:
                        self._result = result
                        self._result_metadata = metadata
                except Exception as e:
                    logger.error(f"Matching error: {e}", exc_info=True)
            else:
                time.sleep(0.01)

    def stop(self) -> None:
        """Stop worker thread."""
        self._active = False


class DualStreamMatcher:
    """Main coordinator for dual stream feature matching with recording."""

    def __init__(
        self,
        ros_topic: str = "/camera/color/image_raw",
        ros_host: str = "localhost",
        ros_port: int = 9090,
        save_path: Optional[str] = None,
    ):
        self.save_path = save_path

        # Components
        self.matcher = FeatureMatcher()

        # Create recorders if save_path provided
        aria_recorder = FrameRecorder(save_path, "aria") if save_path else None
        ros_recorder = FrameRecorder(save_path, "ros") if save_path else None

        self.aria_buffer = FrameBuffer("Aria", aria_recorder)
        self.ros_buffer = FrameBuffer("ROS", ros_recorder)
        self.matching_worker = MatchingWorker(self.matcher)

        # ROS subscriber with recording
        self.ros_subscriber = ROSCameraSubscriber(
            topic=ros_topic,
            host=ros_host,
            port=ros_port,
            callback=self._on_ros_frame,
            save_path=save_path,
        )

        # State
        self.matching_enabled = True
        self.show_matches = True

        # Setup synchronized recording
        if save_path:
            self._setup_sync_recording(save_path)

        logger.info("Dual stream matcher initialized")
        if save_path:
            logger.info(f"Recording to: {save_path}")

    def _setup_sync_recording(self, save_path: str):
        """Setup synchronized pair recording"""
        self.sync_dir = os.path.join(save_path, "synchronized", "frames")
        os.makedirs(self.sync_dir, exist_ok=True)

        self.sync_csv_path = os.path.join(save_path, "synchronized", "sync_data.csv")
        with open(self.sync_csv_path, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "#pair_id",
                    "aria_timestamp [ns]",
                    "ros_timestamp [ns]",
                    "time_diff [ns]",
                    "time_diff [ms]",
                    "num_matches",
                    "stop_layer",
                    "filename",
                ]
            )

        self.sync_pair_count = 0

    def _on_ros_frame(self, frame: np.ndarray, timestamp_ms: int) -> None:
        """Callback for ROS frames with timestamp."""
        self.ros_buffer.update(frame, timestamp_ms)
        self._trigger_matching()

    def on_aria_frame(self, frame: np.ndarray, timestamp_ms: int) -> None:
        """Callback for Aria frames with timestamp."""
        # Rotate and convert Aria frame
        rotated = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        bgr_frame = cv2.cvtColor(rotated, cv2.COLOR_RGB2BGR)

        self.aria_buffer.update(bgr_frame, timestamp_ms)
        self._trigger_matching()

    def _trigger_matching(self) -> None:
        """Trigger matching if both frames are available."""
        if not self.matching_enabled:
            return

        if self.aria_buffer.is_ready() and self.ros_buffer.is_ready():
            aria_data = self.aria_buffer.get_with_timestamp()
            ros_data = self.ros_buffer.get_with_timestamp()

            if aria_data is not None and ros_data is not None:
                self.matching_worker.submit(
                    aria_data.frame,
                    ros_data.frame,
                    aria_data.timestamp_ms,
                    ros_data.timestamp_ms,
                )

    def create_visualization(self) -> np.ndarray:
        """Create visualization with or without matches."""
        aria_data = self.aria_buffer.get_with_timestamp()
        ros_data = self.ros_buffer.get_with_timestamp()

        # Check if frames available
        if aria_data is None or ros_data is None:
            return self._create_placeholder()

        # Get match result
        match_result, metadata = self.matching_worker.get_result()

        # Update FPS
        self.aria_buffer.update_fps()
        self.ros_buffer.update_fps()

        if self.show_matches and match_result is not None:
            # Create match visualization
            visualization = draw_matches_opencv(
                aria_data.frame,
                ros_data.frame,
                match_result["keypoints0"],
                match_result["keypoints1"],
                match_result["matches"],
                max_matches=50,
            )

            # Add info overlay
            num_matches = len(match_result["matches"])
            print(metadata)
            time_diff_ms = metadata["time_diff_ms"] if metadata else 0

            info_text = [
                f"Aria: {self.aria_buffer.fps:.1f} FPS | TS: {aria_data.timestamp_ms}",
                f"ROS: {self.ros_buffer.fps:.1f} FPS | TS: {ros_data.timestamp_ms}",
                f"Time Diff: {time_diff_ms} ms",
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
                    0.6,
                    (0, 255, 0),
                    2,
                )
                y_offset += 25

            # Save synchronized pair if recording enabled
            if self.save_path and match_result:
                self._save_sync_pair(
                    visualization,
                    aria_data.timestamp_ms,
                    ros_data.timestamp_ms,
                    num_matches,
                    match_result["stop_layer"],
                )

            return visualization
        else:
            # Simple side-by-side view
            target_height = 480
            aria_resized = self._resize_frame(aria_data.frame, target_height)
            ros_resized = self._resize_frame(ros_data.frame, target_height)

            # Add labels with timestamps
            self._add_label(aria_resized, f"Aria ({self.aria_buffer.fps:.1f} FPS)")
            self._add_label(ros_resized, f"ROS ({self.ros_buffer.fps:.1f} FPS)")

            # Add timestamp info
            cv2.putText(
                aria_resized,
                f"TS: {aria_data.timestamp_ms}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 0),
                1,
            )
            cv2.putText(
                ros_resized,
                f"TS: {ros_data.timestamp_ms}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 0),
                1,
            )

            # Add match count if available
            if match_result:
                num_matches = len(match_result["matches"])
                cv2.putText(
                    aria_resized,
                    f"Matches: {num_matches}",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 0),
                    2,
                )

            return np.hstack([aria_resized, ros_resized])

    def _save_sync_pair(
        self,
        visualization: np.ndarray,
        aria_ts: int,
        ros_ts: int,
        num_matches: int,
        stop_layer: int,
    ):
        """Save synchronized pair visualization and metadata"""
        filename = f"sync_{self.sync_pair_count}_{aria_ts}.png"
        filepath = os.path.join(self.sync_dir, filename)
        cv2.imwrite(filepath, visualization)

        time_diff_ms = abs(aria_ts - ros_ts)

        with open(self.sync_csv_path, mode="a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    self.sync_pair_count,
                    aria_ts,
                    ros_ts,
                    time_diff_ms,
                    num_matches,
                    stop_layer,
                    filename,
                ]
            )

        self.sync_pair_count += 1

        if self.sync_pair_count % 50 == 0:
            logger.info(f"Saved {self.sync_pair_count} synchronized pairs")

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

        if self.save_path:
            logger.info(f"Recording saved to: {self.save_path}")
            logger.info(f"  - Aria frames: {self.aria_buffer.recorder.frame_count}")
            logger.info(f"  - ROS frames: {self.ros_buffer.recorder.frame_count}")
            logger.info(f"  - Synchronized pairs: {self.sync_pair_count}")

        logger.info("Cleanup complete")


def dual_stream_matcher(project_root: Path, enable_recording: bool = True) -> None:
    """Main execution function."""
    logger.info("\n=== Dual Stream Feature Matcher ===")
    logger.info("Controls:")
    logger.info("  'q' - Quit")
    logger.info("  'm' - Toggle matching on/off")
    logger.info("  'v' - Toggle match visualization")
    logger.info("  's' - Save current frame")
    logger.info("  'r' - Reset statistics")
    logger.info("=" * 30 + "\n")

    # Setup save path
    save_path = None
    if enable_recording:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_path = str(project_root / "recordings" / f"dual_stream_{timestamp}")
        os.makedirs(save_path, exist_ok=True)
        logger.info(f"Recording enabled: {save_path}")

    # Initialize matcher with recording
    matcher = DualStreamMatcher(
        ros_topic="/camera/color/image_raw",
        ros_host="localhost",
        ros_port=9090,
        save_path=save_path,
    )

    # Create window
    cv2.namedWindow("Aria + ROS2 Camera Matching", cv2.WINDOW_NORMAL)

    try:
        # Subscribe to Aria RGB stream
        observer = None
        logger.info("Aria streaming started")

        # Main loop
        while not quit_keypress():
            try:
                # Get Aria frame with timestamp
                aria_frame = observer.get_undistorted_rgb_image()
                aria_timestamp = observer.timestamp_ms

                if aria_frame is not None and aria_timestamp > 0:
                    matcher.on_aria_frame(aria_frame, aria_timestamp)

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
