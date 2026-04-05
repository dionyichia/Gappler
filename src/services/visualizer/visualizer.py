"""
Aria Image Visualizer

Orchestrates camera feed display, ROS2 subscriptions, and overlay renderers.
"""

import logging
import os
import sys
import time
from multiprocessing.synchronize import Event
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from geometry_msgs.msg import Point
from sensor_msgs.msg import CompressedImage

from config import ROS2Topics, VisualizerConfig
from services.ros.image_helper import ImageHelper
from services.visualizer import KeyboardHandler, MenuOverlay, ROSManager
from services.visualizer.renderers import (
    FeatureMatchVisualizer,
    GazeVisualizer,
    ObjectMaskVisualizer,
)
from services.visualizer.utils import create_placeholder

os.environ["QT_QPA_FONTDIR"] = "/usr/share/fonts"

src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

logger = logging.getLogger(__name__)

# How long (seconds) to hold the last received frame before showing a placeholder.
_FRAME_STALE_TIMEOUT = 2.0


class Visualizer:
    """
    Main visualizer for Aria camera images via ROS2.

    Responsibilities:
    - Window lifecycle (setup / display / teardown)
    - Routing incoming ROS messages to the correct renderer
    - Compositing the final frame and handing it to OpenCV
    - Delegating keyboard input to KeyboardHandler
    """

    def __init__(
        self,
        quit_event: Optional[Event],
        filter_topic: ROS2Topics = ROS2Topics.RGB_CAMERA_RAW,
    ):
        self._quit_event = quit_event
        self.current_topic = filter_topic
        self._camera_source: str = "aria"

        # UI state
        self.show_menu = False

        # Per-topic frame cache: topic → (frame, received_at_timestamp)
        self._frame_cache: Dict[ROS2Topics, Tuple[np.ndarray, float]] = {}

        # The frame to composite in the current render tick.
        self._display_frame: Optional[np.ndarray] = None

        # Reference frame used when overlaying gaze on the raw image.
        self._reference_frame: Optional[np.ndarray] = None

        # Renderers
        self._gaze_viz = GazeVisualizer()
        self._match_viz = FeatureMatchVisualizer()
        self._menu = MenuOverlay()

        # Deferred init (requires ROS2 / window)
        self._ros_manager: Optional[ROSManager] = None
        self._keyboard_handler: Optional[KeyboardHandler] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Set up resources and enter the main display loop."""
        self._setup()
        logger.info("Waiting for frames… (Press 'q' to quit, 'm' for menu)")

        try:
            while self._quit_event is None or not self._quit_event.is_set():
                self._render_frame()
                key = cv2.waitKey(1) & 0xFF
                if not self._keyboard_handler.handle(key):
                    break
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        except Exception as e:
            logger.exception(f"Fatal error in main loop {e}")
            raise
        finally:
            self._cleanup()

    def _setup(self) -> None:
        self._setup_window()
        self._setup_ros()
        self._setup_keyboard()

    def _cleanup(self) -> None:
        logger.info("Cleaning up resources…")
        if self._ros_manager:
            self._ros_manager.stop()
        try:
            cv2.destroyAllWindows()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        cv2.namedWindow(VisualizerConfig.DEFAULT_WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(
            VisualizerConfig.DEFAULT_WINDOW_NAME, *VisualizerConfig.DEFAULT_WINDOW_SIZE
        )
        cv2.setWindowProperty(
            VisualizerConfig.DEFAULT_WINDOW_NAME, cv2.WND_PROP_TOPMOST, 1
        )
        cv2.moveWindow(
            VisualizerConfig.DEFAULT_WINDOW_NAME,
            *VisualizerConfig.DEFAULT_WINDOW_POSITION,
        )

    # ------------------------------------------------------------------
    # ROS2
    # ------------------------------------------------------------------

    def _setup_ros(self) -> None:
        self._ros_manager = ROSManager(
            on_raw_image=self._on_raw_image,
            on_undistorted_image=self._on_undistorted_image,
            on_gaze_position=self._on_gaze_position,
            on_aria_mask_bundle=lambda b: self._on_mask_bundle(b, "aria"),
            on_ros_mask_bundle=lambda b: self._on_mask_bundle(b, "ros"),
            on_feature_match=self._on_feature_match,
            on_combined_bundle=self._on_combined_bundle,
        )
        self._ros_manager.start()

    # ---- ROS callbacks ------------------------------------------------

    def _on_raw_image(self, msg: CompressedImage) -> None:
        if self.current_topic in [
            ROS2Topics.RGB_CAMERA_RAW,
            ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE,
        ]:
            frame = self._ingest_compressed_image(msg)
            if self.current_topic == ROS2Topics.RGB_CAMERA_RAW:
                self._set_display_frame(frame)
            elif self.current_topic == ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE:
                self._reference_frame = frame

    def _on_undistorted_image(self, msg: CompressedImage) -> None:
        if self.current_topic == ROS2Topics.RGB_CAMERA_UNDISTORTED:
            self._set_display_frame(self._ingest_compressed_image(msg))

    def _on_gaze_position(self, msg: Point) -> None:
        if self.current_topic == ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE:
            if self._reference_frame is not None:
                gaze_point = self._rotate_gaze_point_90_cw(
                    (msg.x, msg.y), self._reference_frame.shape
                )
                annotated = self._gaze_viz.visualize(self._reference_frame, gaze_point)
                if annotated is not None:
                    self._set_display_frame(annotated)

    def _rotate_gaze_point_90_cw(
        self, point: Tuple[float, float], image_shape: Tuple[int, ...]
    ) -> Tuple[float, float]:
        """Transform a gaze point to match a 90° clockwise rotated image."""
        x, y = point
        h, w = image_shape[:2]
        return (h - y, x)

    def _on_mask_bundle(self, bundle: dict, source: str) -> None:
        """Handle a deserialized image + inference_state bundle.

        Args:
            bundle: The mask bundle containing image and inference state.
            source: 'aria' for RGB_CAMERA_WITH_OBJECT_MASKS,
                    'ros' for ROS_CAMERA_WITH_OBJECT_MASKS.
        """
        expected_topic = (
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS
            if source == "aria"
            else ROS2Topics.ROS_CAMERA_WITH_OBJECT_MASKS
        )
        if self.current_topic != expected_topic:
            return

        image = ImageHelper.uncompress_image(bundle.get("image", b""))
        if image is None:
            logger.warning(f"Mask bundle missing image for source '{source}'")
            return

        frame = ObjectMaskVisualizer.plot_results(image, bundle.get("inference_state"))
        self._set_display_frame(frame)

    def _on_feature_match(self, bundle: dict) -> None:
        if self.current_topic != ROS2Topics.FEATURE_MATCH_RESULTS:
            return

        frame0 = ImageHelper.uncompress_image(bundle.get("frame0", b""))
        frame1 = ImageHelper.uncompress_image(bundle.get("frame1", b""))

        if frame0 is None or frame1 is None:
            logger.warning("Feature match bundle missing frame(s)")
            return

        frame = self._match_viz.draw_matches(
            frame0,
            frame1,
            bundle.get("keypoints0", {}),
            bundle.get("keypoints1", {}),
            bundle.get("matches"),
        )
        self._set_display_frame(frame)

    def _ingest_compressed_image(self, msg: CompressedImage) -> Optional[np.ndarray]:
        """Decode a CompressedImage message into a BGR frame."""
        try:
            frame = ImageHelper.uncompress_image(msg.data)
            if frame is None:
                logger.debug("Received empty or all-black frame, skipping")
                return None
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"Error processing received image: {e}")
            return None

    def _on_combined_bundle(self, bundle: dict) -> None:
        if self.current_topic != ROS2Topics.COMBINED_VISUALIZATION:
            return

        ros_image = ImageHelper.uncompress_image(bundle.get("image", b""))
        if ros_image is None:
            logger.warning("Combined bundle missing ROS image")
            return

        # 1. Render mask onto the ROS frame.
        frame = ObjectMaskVisualizer.plot_results(
            ros_image, bundle.get("inference_state")
        )
        frame = cv2.cvtColor(frame.copy(), cv2.COLOR_RGB2BGR)

        # 2. Render mask onto the Aria reference frame.
        ref_raw = ImageHelper.uncompress_image(bundle.get("reference_image", b""))
        if ref_raw is not None:
            ref_frame = ObjectMaskVisualizer.plot_results(
                ref_raw, bundle.get("aria_inference_state")
            )
            ref_frame = cv2.cvtColor(ref_frame.copy(), cv2.COLOR_RGB2BGR)
        else:
            ref_frame = None

        # 3. Side-by-side with match lines between Aria reference and ROS frame.
        kp0 = bundle.get("keypoints0")  # Aria-side, (K, 2)
        kp1 = bundle.get("keypoints1")  # ROS-side,  (K, 2)

        if ref_frame is not None and kp0 is not None and kp1 is not None and len(kp0):
            identity_matches = np.column_stack(
                [np.arange(len(kp0)), np.arange(len(kp0))]
            )
            combined = self._match_viz.draw_matches(
                ref_frame, frame, kp0, kp1, identity_matches
            )
        elif ref_frame is not None:
            combined = self._match_viz.draw_side_by_side(ref_frame, frame)
        else:
            combined = frame

        self._set_display_frame(combined)

    # ------------------------------------------------------------------
    # Frame cache
    # ------------------------------------------------------------------

    def _set_display_frame(self, frame: Optional[np.ndarray]) -> None:
        """
        Update both the live display frame and the per-topic cache.

        Caching allows _resolve_frame() to keep showing the last good
        frame for up to _FRAME_STALE_TIMEOUT seconds before falling back
        to a placeholder.
        """
        if frame is None:
            return
        self._display_frame = frame
        self._frame_cache[self.current_topic] = (frame, time.monotonic())

    def _resolve_frame(self) -> np.ndarray:
        """
        Return the best available frame for the current topic:
          1. The live frame if it has been set this tick.
          2. The cached frame if it arrived within _FRAME_STALE_TIMEOUT.
          3. A blank placeholder.
        """
        if self._display_frame is not None:
            return self._display_frame

        cached = self._frame_cache.get(self.current_topic)
        if cached is not None:
            frame, received_at = cached
            if time.monotonic() - received_at < _FRAME_STALE_TIMEOUT:
                return frame

        return create_placeholder(*VisualizerConfig.DEFAULT_WINDOW_SIZE)

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def _setup_keyboard(self) -> None:
        self._keyboard_handler = KeyboardHandler(
            on_topic_change=self._on_topic_change,
            on_menu_toggle=self._on_menu_toggle,
            on_save_frame=self._on_save_frame,
            toggle_camera_source=self._toggle_camera_source,
        )

    def _on_topic_change(self, topic: ROS2Topics) -> None:
        # Clear the live frame so we don't flash stale data from the old topic.
        self._display_frame = None
        self.current_topic = topic
        self.show_menu = False
        print(f"Switched to topic: {topic.name}")

    def _on_menu_toggle(self) -> None:
        self.show_menu = not self.show_menu
        print(f"Menu {'opened' if self.show_menu else 'closed'}")

    def _on_save_frame(self) -> None:
        frame = self._resolve_frame()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{timestamp}.png"
        cv2.imwrite(filename, frame)
        logger.info(f"Saved frame to {filename}")
        print(f"Saved frame to {filename}")

    def _toggle_camera_source(self) -> None:
        """Toggle between aria/ros object recognition views."""
        if self.current_topic not in [
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS,
            ROS2Topics.ROS_CAMERA_WITH_OBJECT_MASKS,
        ]:
            return

        if self.current_topic == ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS:
            self.current_topic = ROS2Topics.ROS_CAMERA_WITH_OBJECT_MASKS
            self._camera_source = "ros"
        else:
            self.current_topic = ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS
            self._camera_source = "aria"

        self._display_frame = None  # force cache lookup on next tick
        logger.info(f"Switched object recognition source to: {self._camera_source}")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_frame(self) -> None:
        """Composite the display frame and hand it to OpenCV."""
        display = self._resolve_frame().copy()

        if self.show_menu:
            display = self._menu.draw(display, self.current_topic)

        if self.current_topic in [
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS,
            ROS2Topics.ROS_CAMERA_WITH_OBJECT_MASKS,
        ]:
            label = f"Source: {self._camera_source.upper()}  [TAB to switch]"
            cv2.putText(
                display,
                label,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )

        cv2.imshow(VisualizerConfig.DEFAULT_WINDOW_NAME, display)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def visualize_feed(aria_streaming_started: Event, quit_event: Event) -> None:
    """Entry point for the visualizer process."""
    aria_streaming_started.wait()
    Visualizer(quit_event).run()


if __name__ == "__main__":
    visualize_feed()
