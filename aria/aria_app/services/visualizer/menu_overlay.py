"""
Camera topic selection menu overlay drawn onto OpenCV frames.
"""

from typing import Optional

import cv2
import numpy as np

from config import ROS2Topics


class MenuOverlay:
    """
    Renders a semi-transparent camera topic selection menu over a frame.

    Usage:
        menu = MenuOverlay()
        annotated_frame = menu.draw(base_image, current_topic)
    """

    topics = [
        ("1", "Topic 1 (RGB Camera Raw)", ROS2Topics.RGB_CAMERA_RAW),
        ("2", "Topic 2 (RGB Camera Undistorted)", ROS2Topics.RGB_CAMERA_UNDISTORTED),
        ("3", "Topic 3 (RGB with Gaze)", ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE),
        (
            "4",
            "Topic 4 (RGB with Object Masks)",
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS,
        ),
        ("5", "Topic 5 (Feature Matching)", ROS2Topics.FEATURE_MATCH_RESULTS),
    ]

    menu_width = 400
    menu_height = 500
    font = cv2.FONT_HERSHEY_SIMPLEX

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def draw(
        self,
        base_image: np.ndarray,
        current_topic: Optional[ROS2Topics],
    ) -> np.ndarray:
        """
        Composite the menu onto *base_image* and return the result.

        Args:
            base_image: Background camera frame (not mutated).
            current_topic: Currently active ROS2 topic (highlighted in menu).

        Returns:
            New image with menu overlay applied.
        """
        image = base_image.copy()
        h, w = image.shape[:2]

        menu_x = (w - self.menu_width) // 2
        menu_y = (h - self.menu_height) // 2

        image = self._draw_background(image, menu_x, menu_y)
        self._draw_border(image, menu_x, menu_y)
        self._draw_title(image, menu_x, menu_y)
        self._draw_topic_buttons(image, menu_x, menu_y, current_topic)
        self._draw_instructions(image, menu_x, menu_y)

        return image

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _draw_background(
        self, image: np.ndarray, menu_x: int, menu_y: int
    ) -> np.ndarray:
        """Draw semi-transparent menu background."""
        overlay = image.copy()
        cv2.rectangle(
            overlay,
            (menu_x, menu_y),
            (menu_x + self.menu_width, menu_y + self.menu_height),
            (40, 40, 40),
            -1,
        )
        alpha = 0.85
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        return image

    def _draw_border(self, image: np.ndarray, menu_x: int, menu_y: int) -> None:
        cv2.rectangle(
            image,
            (menu_x, menu_y),
            (menu_x + self.menu_width, menu_y + self.menu_height),
            (200, 200, 200),
            2,
        )

    def _draw_title(self, image: np.ndarray, menu_x: int, menu_y: int) -> None:
        """Draw menu title."""
        title = "Camera Topic Selection"
        title_size = cv2.getTextSize(title, self.font, 0.8, 2)[0]
        title_x = menu_x + (self.menu_width - title_size[0]) // 2
        title_y = menu_y + 40

        cv2.putText(
            image, title, (title_x, title_y), self.font, 0.8, (255, 255, 255), 2
        )

    def _draw_topic_buttons(
        self,
        image: np.ndarray,
        menu_x: int,
        menu_y: int,
        current_topic: Optional[ROS2Topics],
    ) -> None:
        """Draw topic selection buttons."""
        button_height = 50
        button_width = 350
        button_x = menu_x + 25
        start_y = menu_y + 80

        for i, (key, label, topic) in enumerate(self.topics):
            button_y = start_y + i * (button_height + 15)
            is_selected = current_topic == topic

            button_color = (60, 120, 200) if is_selected else (80, 80, 80)
            text_color = (255, 255, 255) if is_selected else (200, 200, 200)

            # Fill + border
            cv2.rectangle(
                image,
                (button_x, button_y),
                (button_x + button_width, button_y + button_height),
                button_color,
                -1,
            )

            # Draw button border
            cv2.rectangle(
                image,
                (button_x, button_y),
                (button_x + button_width, button_y + button_height),
                (150, 150, 150),
                2,
            )

            # Label
            text = f"[{key}] {label}"
            text_size = cv2.getTextSize(text, self.font, 0.6, 1)[0]
            text_x = button_x + 15
            text_y = button_y + (button_height + text_size[1]) // 2

            cv2.putText(image, text, (text_x, text_y), self.font, 0.6, text_color, 1)

    def _draw_instructions(self, image: np.ndarray, menu_x: int, menu_y: int) -> None:
        """Draw menu instructions."""
        instructions = "Press 'M' to close menu | 'Q' to quit"
        inst_size = cv2.getTextSize(instructions, self.font, 0.5, 1)[0]
        inst_x = menu_x + (self.menu_width - inst_size[0]) // 2
        inst_y = menu_y + self.menu_height - 20

        cv2.putText(
            image, instructions, (inst_x, inst_y), self.font, 0.5, (180, 180, 180), 1
        )
