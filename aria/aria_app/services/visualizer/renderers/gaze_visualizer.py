"""
Gaze visualization: projects and renders eye-tracking gaze points onto images.
"""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from config import VisualizerConfig

logger = logging.getLogger(__name__)


class GazeVisualizer:
    """
    Handles projection and rendering of eye-tracking gaze points on camera images.

    Usage:
        visualizer = GazeVisualizer()
        gaze_point, result_image = visualizer.visualize(rgb_image, gaze_point)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def visualize(
        self,
        rgb_image: np.ndarray,
        gaze_point: Tuple[float, float],
        gaze_radius: int = VisualizerConfig.GAZE_POINT_RADIUS,
        gaze_color: Tuple[int, int, int] = VisualizerConfig.GAZE_POINT_COLOR,
    ) -> Optional[np.ndarray]:
        """
        Draw a gaze point circle on an image.

        Args:
            rgb_image: Input RGB image as numpy array.
            gaze_point: (x, y) pixel coordinates.
            gaze_radius: Radius of the gaze circle in pixels.
            gaze_color: BGR color of the gaze circle.

        Returns:
            Image with gaze point drawn on success, or None on failure.
        """
        if rgb_image is None or rgb_image.size == 0:
            return None

        if gaze_point is None:
            return rgb_image

        image = rgb_image.copy()
        gaze_point = tuple(int(c) for c in gaze_point)
        cv2.circle(image, gaze_point, gaze_radius, gaze_color, -1)
        return image
