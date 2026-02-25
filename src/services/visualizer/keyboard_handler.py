"""
Keyboard input handler for the Visualizer main loop.
"""

import logging
from typing import Callable

from config import ROS2Topics

logger = logging.getLogger(__name__)

ESC_KEY = 27
TAB = 9


class KeyboardHandler:
    """
    Translates raw cv2.waitKey() key codes into Visualizer state changes.

    Callbacks are injected so this class stays decoupled from the Visualizer.

    Usage:
        handler = KeyboardHandler(
            on_topic_change=...,
            on_menu_toggle=...,
            on_save_frame=...,
        )
        should_continue = handler.handle(key)
    """

    def __init__(
        self,
        on_topic_change: Callable[[ROS2Topics], None],
        on_menu_toggle: Callable[[], None],
        on_save_frame: Callable[[], None] = None,
        toggle_camera_source: Callable[[], None] = None,
    ):
        self._on_topic_change = on_topic_change
        self._on_menu_toggle = on_menu_toggle
        self._on_save_frame = on_save_frame
        self._toggle_camera_source = toggle_camera_source

        self._topic_keys = {
            ord("1"): ROS2Topics.RGB_CAMERA_RAW,
            ord("2"): ROS2Topics.RGB_CAMERA_UNDISTORTED,
            ord("3"): ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE,
            ord("4"): ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS,
            ord("5"): ROS2Topics.FEATURE_MATCH_RESULTS,
        }

    def handle(self, key: int) -> bool:
        """
        Process a key code and invoke the appropriate callback.

        Args:
            key: Raw key code from cv2.waitKey() & 0xFF.

        Returns:
            False if the application should quit, True otherwise.
        """
        if key in (ESC_KEY, ord("q")):
            logger.info("Quit requested")
            return False

        if key == ord("m"):
            self._on_menu_toggle()
            return True

        if key == TAB:
            self._toggle_camera_source()
            return True

        if key in self._topic_keys:
            topic = self._topic_keys[key]
            self._on_topic_change(topic)
            return True

        if key == ord("s") and self._on_save_frame:
            self._on_save_frame()
            return True

        return True
