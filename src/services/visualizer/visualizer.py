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
from typing import Optional, Tuple

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

# Add src directory to path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

logger = logging.getLogger(__name__)


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
        self._reference_frame: Optional[np.ndarray] = None
        self._display_frame: Optional[np.ndarray] = None

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
        """Initialise window, ROS manager, and keyboard handler."""
        self._setup_window()
        self._setup_ros()
        self._setup_keyboard()

    def _cleanup(self) -> None:
        """Release all resources."""
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
            on_mask_bundle=self._on_mask_bundle,
            on_feature_match=self._on_feature_match,
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
                self._display_frame = frame
            elif self.current_topic == ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE:
                self._reference_frame = frame

    def _on_undistorted_image(self, msg: CompressedImage) -> None:
        if self.current_topic == ROS2Topics.RGB_CAMERA_UNDISTORTED:
            frame = self._ingest_compressed_image(msg)
            self._display_frame = frame

    def _on_gaze_position(self, msg: Point) -> None:
        # If gaze topic is active, draw the gaze point over the reference frame
        if self.current_topic == ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE:
            if self._reference_frame is not None:
                gaze_point = self._rotate_gaze_point_90_cw(
                    (msg.x, msg.y), self._reference_frame.shape
                )
                annotated = self._gaze_viz.visualize(self._reference_frame, gaze_point)
                if annotated is not None:
                    self._display_frame = annotated

    def _rotate_gaze_point_90_cw(
        self, point: Tuple[float, float], image_shape: Tuple[int, ...]
    ) -> Tuple[float, float]:
        """Transform a gaze point to match a 90° clockwise rotated image."""
        x, y = point
        h, w = image_shape[:2]
        return (h - y, x)

    def _on_mask_bundle(self, bundle: dict) -> None:
        """Handle a deserialized image + inference_state bundle."""
        if self.current_topic != ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS:
            return

        source_bundle = bundle.get(self._camera_source, {})
        image = ImageHelper.uncompress_image(source_bundle.get("image", b""))

        if image is None:
            logger.warning(
                f"Mask bundle missing image for source '{self._camera_source}'"
            )
            return

        annotated = ObjectMaskVisualizer.plot_results(
            image, source_bundle.get("inference_state")
        )
        self._display_frame = annotated

    def _on_feature_match(self, bundle: dict) -> None:
        if self.current_topic != ROS2Topics.FEATURE_MATCH_RESULTS:
            return

        frame0 = ImageHelper.uncompress_image(bundle.get("frame0", b""))
        frame1 = ImageHelper.uncompress_image(bundle.get("frame1", b""))

        if frame0 is None or frame1 is None:
            logger.warning("Feature match bundle missing frame(s)")
            return

        self._display_frame = self._match_viz.draw_matches(
            frame0,
            frame1,
            bundle.get("keypoints0", {}),
            bundle.get("keypoints1", {}),
            bundle.get("matches"),
        )

    def _ingest_compressed_image(self, msg: CompressedImage) -> None:
        """Decode a CompressedImage message and store as the latest frame."""
        try:
            frame = ImageHelper.uncompress_image(msg.data)

            if frame is None:
                print("Received empty or all-black frame, skipping")
                return

            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"Error processing received image: {e}")

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
        self.current_topic = topic
        self.show_menu = False
        print(f"Switched to topic: {topic.name}")

    def _on_menu_toggle(self) -> None:
        self.show_menu = not self.show_menu
        print(f"Menu {'opened' if self.show_menu else 'closed'}")

    def _on_save_frame(self) -> None:
        if self._display_frame is None:
            return
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{timestamp}.png"
        cv2.imwrite(filename, self._display_frame)
        logger.info(f"Saved frame to {filename}")
        print(f"Saved frame to {filename}")

    def _toggle_camera_source(self) -> None:
        """Switch between aria/ros object recognition views."""
        self._camera_source = "ros" if self._camera_source == "aria" else "aria"
        logger.info(f"Switched object recognition source to: {self._camera_source}")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_frame(self) -> None:
        """Composite the display frame and hand it to OpenCV."""
        frame = self._display_frame
        if frame is None:
            frame = create_placeholder(*VisualizerConfig.DEFAULT_WINDOW_SIZE)

        display = frame.copy()

        if self.show_menu:
            display = self._menu.draw(display, self.current_topic)

        if self.current_topic == ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS:
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


def visualize_feed(quit_event: Event) -> None:
    """Entry point for the visualizer process."""
    Visualizer(quit_event).run()


if __name__ == "__main__":
    visualize_feed()
