"""
Feature matching visualization: draws keypoint matches between two camera frames.
"""

import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


class FeatureMatchVisualizer:
    """
    Creates side-by-side visualizations of feature matches between two images.

    Supports both match-line overlays and plain side-by-side views.

    Usage:
        viz = FeatureMatchVisualizer()
        display = viz.draw_matches(image0, image1, kpts0, kpts1, matches)
        # or
        display = viz.draw_side_by_side(image0, image1)
    """

    def __init__(self, max_matches: int = 50, target_height: int = 480):
        """
        Args:
            max_matches: Maximum number of match lines to render (for clarity).
            target_height: Height to normalize both images to before combining.
        """
        self.max_matches = max_matches
        self.target_height = target_height
        self._show_matches = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def toggle_matching(self) -> bool:
        """Toggle match-line rendering on/off. Returns new state."""
        self._show_matches = not self._show_matches
        state = "enabled" if self._show_matches else "disabled"
        logger.info(f"Feature match visualization {state}")
        return self._show_matches

    def draw_matches(
        self,
        image0: np.ndarray,
        image1: np.ndarray,
        kpts0,
        kpts1,
        matches,
        stop_layer: Optional[str] = None,
    ) -> np.ndarray:
        """
        Draw feature match lines between two images side-by-side.

        Args:
            image0: Left image.
            image1: Right image.
            kpts0: Keypoints for image0 (numpy array or torch.Tensor, shape Nx2).
            kpts1: Keypoints for image1 (numpy array or torch.Tensor, shape Nx2).
            matches: Match index pairs (numpy array or torch.Tensor, shape Mx2).
            stop_layer: Optional layer name to display in overlay text.

        Returns:
            Combined image with match lines drawn.
        """
        num_matches = len(matches)
        kpts0, kpts1, matches = self._to_numpy(kpts0, kpts1, matches)
        image0, image1, kpts0, kpts1 = self._normalize_heights(
            image0, image1, kpts0, kpts1
        )

        h, w0 = image0.shape[:2]
        _, w1 = image1.shape[:2]
        combined = np.zeros((h, w0 + w1, 3), dtype=np.uint8)
        combined[:, :w0] = image0
        combined[:, w0:] = image1

        if self._show_matches and len(matches) > 0:
            mkpts0 = kpts0[matches[:, 0]].copy()
            mkpts1 = kpts1[matches[:, 1]].copy()

            if len(mkpts0) > self.max_matches:
                idx = np.random.choice(len(mkpts0), self.max_matches, replace=False)
                mkpts0, mkpts1 = mkpts0[idx], mkpts1[idx]

            self._draw_match_lines(combined, mkpts0, mkpts1, w0)

        self._draw_info_overlay(combined, num_matches, stop_layer)
        return combined

    def draw_side_by_side(
        self,
        image0: np.ndarray,
        image1: np.ndarray,
        num_matches: Optional[int] = None,
    ) -> np.ndarray:
        """
        Create a plain side-by-side view without match lines.

        Args:
            image0: Left image.
            image1: Right image.
            num_matches: Optional match count to annotate on image0.

        Returns:
            Combined image.
        """
        from ..utils.image_utils import resize_frame  # local import to avoid cycles

        img0_r = resize_frame(image0, self.target_height)
        img1_r = resize_frame(image1, self.target_height)

        if num_matches is not None:
            cv2.putText(
                img0_r,
                f"Matches: {num_matches}",
                (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 0),
                2,
            )

        return np.hstack([img0_r, img1_r])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_numpy(kpts0, kpts1, matches):
        """Convert torch tensors to numpy arrays if needed."""

        def _maybe_numpy(x):
            if _TORCH_AVAILABLE and isinstance(x, torch.Tensor):
                return x.cpu().numpy()
            return x

        return _maybe_numpy(kpts0), _maybe_numpy(kpts1), _maybe_numpy(matches)

    def _normalize_heights(self, image0, image1, kpts0, kpts1):
        """Resize images to the same height and scale keypoints accordingly."""
        h0, w0 = image0.shape[:2]
        h1, w1 = image1.shape[:2]

        if h0 == h1:
            return image0, image1, kpts0, kpts1

        target_h = max(h0, h1)

        if h0 < target_h:
            scale = target_h / h0
            image0 = cv2.resize(image0, (int(w0 * scale), target_h))
            if kpts0 is not None and len(kpts0) > 0:
                kpts0 = kpts0 * scale

        if h1 < target_h:
            scale = target_h / h1
            image1 = cv2.resize(image1, (int(w1 * scale), target_h))
            if kpts1 is not None and len(kpts1) > 0:
                kpts1 = kpts1 * scale

        return image0, image1, kpts0, kpts1

    @staticmethod
    def _draw_match_lines(
        combined: np.ndarray,
        mkpts0: np.ndarray,
        mkpts1: np.ndarray,
        offset_x: int,
    ) -> None:
        """Draw coloured match lines and keypoint circles on combined image."""
        n = len(mkpts0)
        for i in range(n):
            pt0 = tuple(mkpts0[i].astype(int))
            pt1 = tuple((mkpts1[i] + [offset_x, 0]).astype(int))

            ratio = i / max(n - 1, 1)
            color = (
                int(255 * (1 - ratio)),  # B
                int(255 * ratio * 0.5),  # G
                int(255 * ratio),  # R
            )

            cv2.line(combined, pt0, pt1, color, 1, cv2.LINE_AA)
            cv2.circle(combined, pt0, 3, color, -1, cv2.LINE_AA)
            cv2.circle(combined, pt1, 3, color, -1, cv2.LINE_AA)

    @staticmethod
    def _draw_info_overlay(
        image: np.ndarray,
        num_matches: Optional[int],
        stop_layer: Optional[str],
    ) -> None:
        """Overlay match count and layer info text."""
        lines = []
        if num_matches is not None:
            lines.append(f"Matches: {num_matches}")
        if stop_layer is not None:
            lines.append(f"Layer: {stop_layer}")

        for y_offset, text in enumerate(lines, start=1):
            cv2.putText(
                image,
                text,
                (10, y_offset * 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
