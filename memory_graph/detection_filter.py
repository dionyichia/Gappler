"""S2: drop detections that should never become objects (part of T6.3c).

Upstream's version (map_utils.py:183) sorts the detections into a new list, then
uses the sorted positions to index the original arrays (map_utils.py:219-245),
which is only right if the input was already sorted. Here the detections are
sorted once and every array is indexed from that one order.
"""

from __future__ import annotations

from typing import AbstractSet, Tuple

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.stage_types import Detections


def sort_by_confidence(dets: Detections) -> Detections:
    """Highest confidence first. Ties keep their input order (a stable sort)."""
    order = np.argsort(-dets.conf, kind="stable")
    return dets.take(order)


def filter_detections(
    dets: Detections,
    image_shape: Tuple[int, int],
    targets: AbstractSet[str],
    cfg: MemoryGraphConfig,
) -> Detections:
    """Sorted, filtered detections.

    A detection is dropped if any of these holds:
      1. its label is a background class and cfg.skip_bg is on;
      2. its box covers less than cfg.min_box_area_ratio of the image;
      3. its confidence is below cfg.confidence_threshold and its label is
         not in `targets`. Targets are kept at any confidence.

    `targets` is passed in, not read from a global, because it changes per task.
    """
    dets = sort_by_confidence(dets)
    if len(dets) == 0:
        return dets
    h, w = image_shape
    widths = np.clip(dets.xyxy[:, 2] - dets.xyxy[:, 0], 0, None)
    heights = np.clip(dets.xyxy[:, 3] - dets.xyxy[:, 1], 0, None)
    area_ok = widths * heights >= cfg.min_box_area_ratio * h * w

    is_target = np.array([lbl in targets for lbl in dets.label], dtype=bool)
    conf_ok = (dets.conf >= cfg.confidence_threshold) | is_target

    bg = set(cfg.bg_classes) if cfg.skip_bg else set()
    not_bg = np.array([lbl not in bg for lbl in dets.label], dtype=bool)

    return dets.take(np.flatnonzero(area_ok & conf_ok & not_bg))
