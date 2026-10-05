"""The data passed between stages (T6.3a).

From cmg_construction_pipeline.md section 3. Each stage is a function from one of
these to another, so each can be built and tested on its own.

Frames: camera axes follow OpenCV (x right, y down, z forward). The world frame
has z up. T_world_cam maps camera points to world points (camera-to-world).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class Observation:
    """One posed RGB-D photo. S0's output."""

    rgb: np.ndarray            # uint8 (H, W, 3), RGB order, not BGR
    depth: np.ndarray          # float32 (H, W), metres along the optical axis, 0 = invalid
    K: np.ndarray              # (3, 3) pinhole intrinsics of the colour image
    T_world_cam: np.ndarray    # (4, 4) camera-to-world
    frame_id: int              # unique, increasing, never reset
    timestamp: float = 0.0     # seconds, capture time

    def __post_init__(self) -> None:
        h, w = self.depth.shape
        if self.rgb.shape != (h, w, 3):
            raise ValueError(f"rgb {self.rgb.shape} does not match depth {self.depth.shape}")
        if self.K.shape != (3, 3) or self.T_world_cam.shape != (4, 4):
            raise ValueError("K must be 3x3 and T_world_cam 4x4")

    @property
    def camera_position(self) -> np.ndarray:
        return self.T_world_cam[:3, 3]


@dataclass
class Detections:
    """Labelled boxes in one image. S1 makes them, S2 filters them, S4 adds masks.

    After S2 the arrays are sorted by confidence, highest first. Every per-detection
    array has the same length N, and `take` keeps them that way.
    """

    xyxy: np.ndarray                    # float (N, 4), pixel coordinates
    conf: np.ndarray                    # float (N,)
    class_id: np.ndarray                # int (N,), index into the vocabulary
    label: List[str]                    # length N
    masks: Optional[np.ndarray] = None  # bool (N, H, W), filled by S4

    def __post_init__(self) -> None:
        self.xyxy = np.asarray(self.xyxy, dtype=np.float64).reshape(-1, 4)
        self.conf = np.asarray(self.conf, dtype=np.float64).reshape(-1)
        self.class_id = np.asarray(self.class_id, dtype=np.int64).reshape(-1)
        self.label = list(self.label)
        n = len(self.xyxy)
        if not (len(self.conf) == len(self.class_id) == len(self.label) == n):
            raise ValueError("xyxy, conf, class_id and label must have the same length")
        if self.masks is not None and len(self.masks) != n:
            raise ValueError("masks must have one entry per detection")

    def __len__(self) -> int:
        return len(self.xyxy)

    def take(self, idx) -> "Detections":
        """The detections at `idx`, in that order, with every array kept aligned."""
        idx = np.asarray(idx, dtype=np.int64).reshape(-1)
        return Detections(
            xyxy=self.xyxy[idx],
            conf=self.conf[idx],
            class_id=self.class_id[idx],
            label=[self.label[i] for i in idx],
            masks=None if self.masks is None else self.masks[idx],
        )

    @staticmethod
    def empty(image_shape=None) -> "Detections":
        masks = None if image_shape is None else np.zeros((0, *image_shape), dtype=bool)
        return Detections(np.zeros((0, 4)), np.zeros(0), np.zeros(0, dtype=np.int64), [], masks)


@dataclass
class OrientedBox:
    """A 3D box: centre, rotation whose columns are the box axes, full side lengths."""

    center: np.ndarray   # (3,)
    R: np.ndarray        # (3, 3)
    extent: np.ndarray   # (3,), full lengths along R's columns

    @property
    def volume(self) -> float:
        return float(np.prod(self.extent))

    @property
    def half_diagonal(self) -> float:
        """Radius of the smallest sphere around the box centre that holds the box."""
        return float(np.linalg.norm(self.extent) / 2.0)

    def corners(self) -> np.ndarray:
        signs = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], dtype=float)
        return self.center + (signs * (self.extent / 2.0)) @ self.R.T


@dataclass
class Candidate:
    """One detection lifted into 3D and cleaned. S7 to S9's output, S10's input."""

    points: np.ndarray       # float (M, 3), world frame
    colors: np.ndarray       # float (M, 3), in [0, 1]
    box: OrientedBox
    label: str
    conf: float
    class_id: int = -1
    clip: Optional[np.ndarray] = None   # (D,), L2-normalised, from S6
    detection_index: int = -1           # which detection in the photo it came from
    mask_pixels: int = 0                # mask area in the image, for the edge payload
