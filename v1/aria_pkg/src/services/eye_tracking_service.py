# services/eye_tracking_service.py
import numpy as np
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class EyeTrackingService:
    """Service for eye tracking data processing"""

    @staticmethod
    def load_eye_tracking_data(txt_path: str) -> np.ndarray:
        """Load eye tracking coordinates from text file"""
        coordinates = []
        try:
            with open(txt_path, "r") as f:
                for line in f:
                    x, y = map(float, line.strip().split(","))
                    coordinates.append((y, x))  # Note: swapped for image coordinates
        except Exception as e:
            logger.error(f"Failed to load eye tracking from {txt_path}: {e}")
            raise

        return np.array(coordinates)

    @staticmethod
    def find_closest_mask(
        eye_tracking_path: str,
        masks: np.ndarray,
    ) -> int:
        """
        Find mask closest to eye tracking gaze points

        Args:
            eye_tracking_path: Path to eye tracking data
            masks: Array of segmentation masks

        Returns:
            Index of closest mask
        """
        eye_tracking_results = EyeTrackingService.load_eye_tracking_data(
            eye_tracking_path
        )

        mask_distances = []
        for mask in masks:
            mask_points = np.argwhere(mask > 0)
            mask_center = np.mean(mask_points, axis=0)

            distances = [
                np.linalg.norm(eye_point - mask_center)
                for eye_point in eye_tracking_results
            ]
            avg_distance = np.mean(distances)
            mask_distances.append(avg_distance)

        closest_index = int(np.argmin(mask_distances))
        logger.info(f"Closest mask to gaze: index {closest_index}")
        return closest_index

    @staticmethod
    def find_position_bbox(
        eye_tracking_path: str,
        image_shape: Tuple[int, int],
        box_size: int = 150,
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Get bounding box around eye tracking center

        Args:
            eye_tracking_path: Path to eye tracking data
            image_shape: (height, width) of image
            box_size: Size of bounding box

        Returns:
            Tuple of (center_point, [x_min, y_min, x_max, y_max])
        """
        eye_tracking_results = EyeTrackingService.load_eye_tracking_data(
            eye_tracking_path
        )
        mid_point = np.mean(eye_tracking_results, axis=0)

        x, y = mid_point
        half_size = box_size // 2

        x_min = max(int(x - half_size), 0)
        y_min = max(int(y - half_size), 0)
        x_max = min(int(x + half_size), image_shape[1])
        y_max = min(int(y + half_size), image_shape[0])

        bbox = [x_min, y_min, x_max, y_max]
        logger.info(f"Position bbox: {bbox}")

        return mid_point, bbox
