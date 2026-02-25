"""
SAM (Segment Anything Model) object mask and bounding box visualization.
"""

import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np

from config import VisualizerConfig

logger = logging.getLogger(__name__)


class ObjectMaskVisualizer:
    """
    Renders SAM detection results (masks + bounding boxes) onto images.

    Usage:
        annotated = ObjectMaskVisualizer.plot_results(image, results)
    """

    def __init__(self, colors: Optional[List[Tuple[int, int, int]]] = None):
        """
        Args:
            colors: Ordered list of BGR color tuples to cycle through per object.
                    Defaults to a built-in palette if not provided.
        """
        self.colors = colors or VisualizerConfig.CV2_COLORS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def plot_results(img: np.ndarray, results: Optional[dict]) -> np.ndarray:
        """
        Overlay masks and bounding boxes for all detected objects.

        Args:
            img: Input image (BGR numpy array).
            results: Detection dict with keys: 'scores', 'masks', 'boxes'.

        Returns:
            Annotated image copy.
        """
        img_cv = cv2.cvtColor(img.copy(), cv2.COLOR_RGB2BGR)

        if results is None:
            logger.debug("No results to plot")
            return img_cv

        if "scores" not in results or len(results["scores"]) == 0:
            logger.debug("No objects detected")
            return img_cv

        h, w = img_cv.shape[:2]
        nb_objects = len(results["scores"])
        logger.debug(f"Plotting {nb_objects} object(s)")

        for i in range(nb_objects):
            color = VisualizerConfig.CV2_COLORS[i % len(VisualizerConfig.CV2_COLORS)]
            mask = results["masks"][i].squeeze(0).cpu().numpy()
            prob = results["scores"][i].item()
            box = results["boxes"][i].cpu().numpy()

            img_cv = ObjectMaskVisualizer._plot_mask(
                img_cv, mask, color=color, alpha=0.5
            )
            img_cv = ObjectMaskVisualizer._plot_bbox(
                img_cv,
                h,
                w,
                box,
                text=f"(id={i}, prob={prob:.2f})",
                color=color,
            )

        return img_cv

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _plot_mask(
        img: np.ndarray,
        mask: np.ndarray,
        color: Tuple[int, int, int],
        alpha: float = 0.5,
    ) -> np.ndarray:
        """
        Apply a semi-transparent colored mask overlay.

        Args:
            img: Input image.
            mask: Binary mask (H x W).
            color: BGR color tuple.
            alpha: Blend strength of the mask overlay.

        Returns:
            Image with mask blended in.
        """
        im_h, im_w = mask.shape
        colored_mask = np.zeros((im_h, im_w, 3), dtype=np.uint8)
        colored_mask[mask > 0] = color

        mask_binary = (mask > 0).astype(np.uint8)
        for c in range(3):
            img[:, :, c] = np.where(
                mask_binary,
                img[:, :, c] * (1 - alpha) + colored_mask[:, :, c] * alpha,
                img[:, :, c],
            )
        return img

    @staticmethod
    def _plot_bbox(
        img: np.ndarray,
        img_height: int,
        img_width: int,
        box: np.ndarray,
        box_format: str = "XYXY",
        relative_coords: bool = False,
        color: Tuple[int, int, int] = (0, 0, 255),
        text: Optional[str] = None,
        thickness: int = 2,
    ) -> np.ndarray:
        """
        Draw a bounding box with an optional text label.

        Args:
            img: Input image.
            img_height: Image height (used for relative coord conversion).
            img_width: Image width.
            box: Box coordinates array.
            box_format: One of 'XYXY', 'XYWH', or 'CxCyWH'.
            relative_coords: If True, coordinates are in [0, 1] range.
            color: BGR box color.
            text: Optional label string.
            thickness: Rectangle line thickness.

        Returns:
            Image with bounding box drawn.
        """
        if box_format == "XYXY":
            x, y, x2, y2 = box
            w, h = x2 - x, y2 - y
        elif box_format == "XYWH":
            x, y, w, h = box
        elif box_format == "CxCyWH":
            cx, cy, w, h = box
            x, y = cx - w / 2, cy - h / 2
        else:
            raise ValueError(f"Invalid box_format: {box_format}")

        if relative_coords:
            x, w = x * img_width, w * img_width
            y, h = y * img_height, h * img_height

        x, y, w, h = int(x), int(y), int(w), int(h)
        cv2.rectangle(img, (x, y), (x + w, y + h), color, thickness)

        if text is not None:
            ObjectMaskVisualizer._draw_text_with_background(img, text, (x, y), color)

        return img

    @staticmethod
    def _draw_text_with_background(
        img: np.ndarray,
        text: str,
        position: Tuple[int, int],
        bg_color: Tuple[int, int, int],
    ) -> None:
        """
        Draw text with a solid background rectangle for readability.

        Args:
            img: Image to draw on (modified in-place).
            text: Text string.
            position: Top-left (x, y) anchor.
            bg_color: Background fill color (BGR).
        """
        x, y = position
        (text_w, text_h), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        cv2.rectangle(
            img,
            (x, y - text_h - baseline - 5),
            (x + text_w, y),
            bg_color,
            -1,
        )
        cv2.putText(
            img, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
        )
