"""S3: is this photo worth keeping as an anchor (T6.5a, T6.5).

This is what keeps the graph sparse. Upstream: map.py:513, with 1 m and 45
degrees hardcoded.

The gate has two halves, used in this order per photo (T6.5, D-MG12):

    1. pose half, `pose_moved`: the first photo, or the camera moved or turned
       past the limits since the last accepted photo. Costs no inference, so it
       runs before SAM 3, and a photo that fails it skips everything from S1 on.
    2. label half, inside `should_accept`: a photo with no detections left
       after S2 is rejected. It runs after SAM 3, so a rejection here saves only
       S5 onward.

`should_accept` is both halves at once plus upstream's third rule, a target in
view. With the pose half first, that rule only matters for photos that passed
the pose half anyway, so it no longer adds a photo on its own (D-MG12).
"""

from __future__ import annotations

from typing import AbstractSet, Iterable, Optional

import numpy as np

from memory_graph.config import MemoryGraphConfig


def rotation_angle(R_a: np.ndarray, R_b: np.ndarray) -> float:
    """The angle in radians of the rotation that takes R_a to R_b."""
    cos = (np.trace(R_a.T @ R_b) - 1.0) / 2.0
    return float(np.arccos(np.clip(cos, -1.0, 1.0)))


def pose_moved(
    T_world_cam: np.ndarray,
    last_accepted: Optional[np.ndarray],
    cfg: MemoryGraphConfig,
) -> bool:
    """The gate's pose half: True if this is the first photo, or the camera moved
    more than cfg.gate_translation_m or turned more than cfg.gate_rotation_rad
    since `last_accepted`."""
    if last_accepted is None:
        return True
    if np.linalg.norm(T_world_cam[:3, 3] - last_accepted[:3, 3]) > cfg.gate_translation_m:
        return True
    return rotation_angle(last_accepted[:3, :3], T_world_cam[:3, :3]) > cfg.gate_rotation_rad


def should_accept(
    T_world_cam: np.ndarray,
    labels: Iterable[str],
    last_accepted: Optional[np.ndarray],
    targets: AbstractSet[str],
    cfg: MemoryGraphConfig,
) -> bool:
    """Pure decision for one photo.

    `labels` are the photo's labels after S2. `last_accepted` is the pose of the
    last accepted photo, or None if none has been accepted yet. `targets` holds
    the target and related classes of the current task.

    Reject if no detections are left. Otherwise accept if this is the first photo,
    the camera moved more than cfg.gate_translation_m, turned more than
    cfg.gate_rotation_rad, or a target class is in view.
    """
    labels = list(labels)
    if not labels:
        return False
    if pose_moved(T_world_cam, last_accepted, cfg):
        return True
    return any(lbl in targets for lbl in labels)


class AnchorGate:
    """Holds the last accepted pose between photos.

    Call `check` for each photo. Call `commit` only once the photo has actually
    been stored as an anchor (end of S12), so the last accepted pose moves only
    on accept, as upstream does.
    """

    def __init__(self, cfg: MemoryGraphConfig) -> None:
        self.cfg = cfg
        self.last_accepted: Optional[np.ndarray] = None

    def check(self, T_world_cam: np.ndarray, labels: Iterable[str], targets: AbstractSet[str]) -> bool:
        return should_accept(T_world_cam, labels, self.last_accepted, targets, self.cfg)

    def check_pose(self, T_world_cam: np.ndarray) -> bool:
        """The pose half only, to call before SAM 3. Call `check` with the
        photo's labels after S2 for the full decision."""
        return pose_moved(T_world_cam, self.last_accepted, self.cfg)

    def commit(self, T_world_cam: np.ndarray) -> None:
        self.last_accepted = np.array(T_world_cam, dtype=float, copy=True)
