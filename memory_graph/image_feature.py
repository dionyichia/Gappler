"""S6: one appearance vector per detection (part of T6.3f).

Crop each box with padding, encode the crops, L2-normalise. The encoder is passed
in. The real one is OpenClipEncoder in clip_encoder.py: open_clip ViT-B-32
(laion2b_s34b_b79k), as upstream, D-MG7 in docs/MEMORY_GRAPH_DESIGN.md. It is
kept in its own file so this one works without torch. Any object with an
`encode` method that maps a list of RGB crops to an (N, D) array works, so the
model can be changed later.

T6.3f is done only once the real encoder passes its test on real photos: two
crops of the same chair score above 0.8, a chair against a sink clearly lower.
The test is in tests/test_clip_encoder.py and skips until the photos exist.
"""

from __future__ import annotations

from typing import List, Protocol, Sequence

import numpy as np

from memory_graph.config import MemoryGraphConfig


class ImageEncoder(Protocol):
    def encode(self, crops: Sequence[np.ndarray]) -> np.ndarray:
        """RGB uint8 crops, any sizes -> (N, D) float array."""
        ...


def padded_crops(rgb: np.ndarray, xyxy: np.ndarray, pad_ratio: float) -> List[np.ndarray]:
    """Crop each box, padded on each side by pad_ratio of its own width and
    height, clamped to the image. Upstream pads a fixed 20 px (map_utils.py:95),
    which means less context at higher resolution. Each crop is at least 1x1."""
    h, w = rgb.shape[:2]
    crops = []
    for x1, y1, x2, y2 in np.asarray(xyxy, dtype=float).reshape(-1, 4):
        px = (x2 - x1) * pad_ratio
        py = (y2 - y1) * pad_ratio
        left = int(np.clip(np.floor(x1 - px), 0, w - 1))
        top = int(np.clip(np.floor(y1 - py), 0, h - 1))
        right = int(np.clip(np.ceil(x2 + px), left + 1, w))
        bottom = int(np.clip(np.ceil(y2 + py), top + 1, h))
        crops.append(rgb[top:bottom, left:right])
    return crops


def l2_normalise(vectors: np.ndarray) -> np.ndarray:
    """Rows scaled to length 1. An all-zero row stays zero instead of becoming NaN."""
    vectors = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)


def image_features(
    rgb: np.ndarray, xyxy: np.ndarray, encoder: ImageEncoder, cfg: MemoryGraphConfig
) -> np.ndarray:
    """(N, D) L2-normalised features, one per box. Empty input gives (0, 0)."""
    if len(xyxy) == 0:
        return np.zeros((0, 0))
    features = np.asarray(encoder.encode(padded_crops(rgb, xyxy, cfg.crop_pad_ratio)))
    if features.ndim != 2 or len(features) != len(xyxy):
        raise ValueError(f"encoder returned shape {features.shape} for {len(xyxy)} crops")
    return l2_normalise(features)
