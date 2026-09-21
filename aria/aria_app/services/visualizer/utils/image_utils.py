"""
Image utility functions for decoding, resizing, and labeling frames.
"""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def resize_frame(frame: np.ndarray, target_height: int) -> np.ndarray:
    """
    Resize a frame to a target height while maintaining aspect ratio.

    Args:
        frame: Input image
        target_height: Desired output height in pixels

    Returns:
        Resized image
    """
    h, w = frame.shape[:2]
    scale = target_height / h
    return cv2.resize(frame, (int(w * scale), target_height))


def create_placeholder(width: int = 640, height: int = 480) -> np.ndarray:
    """
    Create a black placeholder image with a 'Waiting for frames...' message.

    Args:
        width: Image width
        height: Image height

    Returns:
        Placeholder image
    """
    placeholder = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(
        placeholder,
        "Waiting for frames...",
        (150, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
    )
    return placeholder
