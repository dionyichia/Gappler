"""S4 erosion and S5 mask cleanup (part of T6.3d).

The box-to-mask model itself (S4's segmenter) is not here yet: which model
(MobileSAM as upstream, or the SAM 3 the arm pipeline already runs) is still
open. Anything that returns one bool mask per box can feed these functions.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.stage_types import Detections


def erode_one_pixel(masks: np.ndarray) -> np.ndarray:
    """Keep a pixel only if its whole 3x3 neighbourhood is set.

    Same result as upstream's conv2d(mask, ones(3, 3)) == 9 with zero padding
    (map.py:630), so pixels on the image border are always removed. Do not skip
    this: edge pixels sit on depth jumps and back-project onto the wall behind,
    which gives the point cloud long tails.
    """
    masks = np.asarray(masks, dtype=bool)
    if masks.ndim == 2:
        return erode_one_pixel(masks[None])[0]
    n, h, w = masks.shape
    padded = np.zeros((n, h + 2, w + 2), dtype=bool)
    padded[:, 1:-1, 1:-1] = masks
    out = np.ones_like(masks)
    for dy in range(3):
        for dx in range(3):
            out &= padded[:, dy:dy + h, dx:dx + w]
    return out


def _box_area(xyxy: np.ndarray) -> np.ndarray:
    return np.clip(xyxy[:, 2] - xyxy[:, 0], 0, None) * np.clip(xyxy[:, 3] - xyxy[:, 1], 0, None)


def kept_mask_indices(dets: Detections, cfg: MemoryGraphConfig) -> np.ndarray:
    """Which detections survive mask filtering (map_utils.py:257), in order.

    Walks the detections in confidence order. Expects S2's sorted output.
    A mask is dropped if its area is below min(ratio * H * W, threshold px), or
    if its IoU with an already kept mask is above cfg.mask_iou_threshold.
    """
    if dets.masks is None:
        raise ValueError("mask filtering needs masks; run the segmenter (S4) first")
    n = len(dets)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    h, w = dets.masks.shape[1:]
    min_area = min(cfg.mask_area_ratio * h * w, cfg.mask_area_threshold_px)
    flat = dets.masks.reshape(n, -1)
    areas = flat.sum(axis=1)
    kept = []
    for i in range(n):
        if areas[i] < min_area:
            continue
        duplicate = False
        for j in kept:
            inter = np.count_nonzero(flat[i] & flat[j])
            union = areas[i] + areas[j] - inter
            if union > 0 and inter / union > cfg.mask_iou_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(i)
    return np.asarray(kept, dtype=np.int64)


def filter_masks(dets: Detections, cfg: MemoryGraphConfig) -> Detections:
    """Drop tiny masks and near-duplicate masks. See kept_mask_indices."""
    return dets.take(kept_mask_indices(dets, cfg))


def subtract_contained(dets: Detections, cfg: MemoryGraphConfig) -> Detections:
    """Cut objects out of the objects that contain them (map_utils.py:295).

    If box j is mostly inside box i (overlap / area_j > inner and
    overlap / area_i < outer), then mask_i loses mask_j's pixels: the cup is cut
    out of the table. The test is on boxes, the cut is on masks.
    """
    if dets.masks is None:
        raise ValueError("subtract_contained needs masks; run the segmenter (S4) first")
    n = len(dets)
    if n < 2:
        return dets
    xyxy = dets.xyxy
    area = _box_area(xyxy)
    lt = np.maximum(xyxy[:, None, :2], xyxy[None, :, :2])
    rb = np.minimum(xyxy[:, None, 2:], xyxy[None, :, 2:])
    inter = np.prod(np.clip(rb - lt, 0, None), axis=2)          # inter[i, j]
    with np.errstate(divide="ignore", invalid="ignore"):
        frac_of_j = np.where(area[None, :] > 0, inter / area[None, :], 0.0)
        frac_of_i = np.where(area[:, None] > 0, inter / area[:, None], 0.0)
    contains = (frac_of_j > cfg.contain_inner_ratio) & (frac_of_i < cfg.contain_outer_ratio)
    np.fill_diagonal(contains, False)

    original = dets.masks
    masks = original.copy()
    for i, j in zip(*np.nonzero(contains)):
        masks[i] &= ~original[j]
    out = dets.take(np.arange(n))
    out.masks = masks
    return out


def clean_masks(dets: Detections, cfg: MemoryGraphConfig) -> Tuple[Detections, np.ndarray]:
    """S4 erosion then S5, in upstream's order.

    Returns the cleaned detections and, for each one, its index in the input, so
    the caller can realign anything held outside Detections (image features).
    """
    if dets.masks is None:
        raise ValueError("clean_masks needs masks; run the segmenter (S4) first")
    work = dets.take(np.arange(len(dets)))
    if cfg.erode_masks:
        work.masks = erode_one_pixel(work.masks)
    kept = kept_mask_indices(work, cfg)
    return subtract_contained(work.take(kept), cfg), kept
