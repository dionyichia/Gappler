# models/feature_matcher.py
import numpy as np
from typing import Tuple, List
import logging

from feature_matching import (
    superglue_matching_init,
    superglue,
    calculate_matching_points_in_box,
    calculate_mid_kpts,
)

logger = logging.getLogger(__name__)


class FeatureMatcher:
    """Handles feature matching between two camera views"""

    def __init__(self):
        self.matching, self.timer = superglue_matching_init()
        logger.info("FeatureMatcher initialized")

    def match_object_between_views(
        self,
        img0_path: str,
        img1_path: str,
        bbox: List[float],
        output_path: str,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Match features between two camera views

        Args:
            img0_path: Path to first image (AR glasses)
            img1_path: Path to second image (robot camera)
            bbox: Bounding box in first image
            output_path: Path to save visualization

        Returns:
            Tuple of (keypoints0, keypoints1, confidence)
        """
        mkpts0, mkpts1, mconf = superglue(
            self.matching,
            img0_path,
            img1_path,
            bbox,
            self.timer,
            output_path,
        )

        logger.info(f"Matched {len(mkpts0)} keypoints between views")
        return mkpts0, mkpts1, mconf

    def find_target_in_boxes(
        self,
        matched_keypoints: np.ndarray,
        boxes: np.ndarray,
    ) -> Tuple[List[int], int]:
        """
        Find which bounding box contains most matched keypoints

        Args:
            matched_keypoints: Keypoints in second view
            boxes: Bounding boxes in second view

        Returns:
            Tuple of (points_per_box, best_box_index)
        """
        points_per_bbox, max_bbox_index = calculate_matching_points_in_box(
            matched_keypoints, boxes
        )

        logger.info(
            f"Box {max_bbox_index} has most matches: {points_per_bbox[max_bbox_index]} points"
        )
        return points_per_bbox, max_bbox_index

    def calculate_center(self, keypoints: np.ndarray) -> np.ndarray:
        """Calculate center point of keypoints"""
        return calculate_mid_kpts(keypoints)
