# utils/visualization.py
import cv2
import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class Visualizer:
    """Utilities for visualization"""

    @staticmethod
    def draw_target_center(
        image: np.ndarray,
        masks: np.ndarray,
        index: int,
        color: Tuple[int, int, int] = (255, 255, 0),
        radius: int = 10,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Draw target center point on image

        Args:
            image: Input image
            masks: Segmentation masks
            index: Index of mask to draw
            color: BGR color tuple
            radius: Circle radius

        Returns:
            Tuple of (annotated_image, center_point)
        """
        mask_points = np.argwhere(masks[index] > 0)
        mask_center = np.mean(mask_points, axis=0).astype(int)

        annotated_image = image.copy()
        cv2.circle(
            annotated_image,
            (mask_center[1], mask_center[0]),
            radius=radius,
            color=color,
            thickness=-1,
        )

        center_xy = mask_center[::-1]  # Convert to (x, y)
        logger.info(f"Drew target center at {center_xy}")

        return annotated_image, center_xy

    @staticmethod
    def draw_eye_tracking_bbox(
        image: np.ndarray,
        bbox: List[int],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2,
    ) -> np.ndarray:
        """Draw bounding box on image"""
        x_min, y_min, x_max, y_max = bbox
        annotated_image = image.copy()
        cv2.rectangle(
            annotated_image,
            (x_min, y_min),
            (x_max, y_max),
            color,
            thickness,
        )
        return annotated_image
