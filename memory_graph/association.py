"""S10: which stored object, if any, is each new candidate (T6.4a and T6.4b).

Geometry half (T6.4a): the overlap score. For each candidate and stored object
whose 3D boxes touch, the fraction of the candidate's points that have a stored
point within cfg.match_radius_m (pointcloud.py:615).

Decision half (T6.4b): combine overlap with appearance,
    score = (1 + phys_bias) * overlap + (1 - phys_bias) * appearance
(map.py:838) and match each candidate to at most one object. With upstream's
weights appearance alone tops out at 0.5, below the 0.6 threshold, so a match
always needs some 3D overlap (D-MG2).

Two candidates from one photo may land on the same object: decided 2026-10-07,
greedy as upstream (D-MG8). cfg.association_mode picks "greedy" (upstream,
map_utils.py:377) or "one_to_one", which is kept so the choice can be changed.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

from memory_graph.config import MemoryGraphConfig
from memory_graph.stage_types import Candidate, OrientedBox


class StoredObject(Protocol):
    """What S10 needs from an object already in the graph."""

    points: np.ndarray
    box: OrientedBox
    clip: Optional[np.ndarray]


# ---------------------------------------------------------------- geometry

def boxes_intersect(a: OrientedBox, b: OrientedBox) -> bool:
    """Separating-axis test for two oriented boxes. Touching counts as
    intersecting. Upstream does the same test on boxes rebuilt from their
    corners (pointcloud.py:483)."""
    axes = [a.R[:, i] for i in range(3)] + [b.R[:, i] for i in range(3)]
    for i in range(3):
        for j in range(3):
            cross = np.cross(a.R[:, i], b.R[:, j])
            norm = np.linalg.norm(cross)
            if norm > 1e-9:                    # parallel edges add no new axis
                axes.append(cross / norm)
    d = b.center - a.center
    ha, hb = a.extent / 2.0, b.extent / 2.0
    for axis in axes:
        ra = np.sum(ha * np.abs(a.R.T @ axis))
        rb = np.sum(hb * np.abs(b.R.T @ axis))
        if abs(d @ axis) > ra + rb + 1e-9:
            return False
    return True


def overlap_matrix(
    candidates: Sequence[Candidate], objects: Sequence[StoredObject], cfg: MemoryGraphConfig
) -> np.ndarray:
    """(C, O) overlap scores in [0, 1]. 0 for pairs whose boxes do not touch.

    Upstream compares every candidate with every object. Here a k-d tree on the
    object box centres finds the few objects close enough to possibly touch each
    candidate first, so the cost follows nearby pairs, not candidates x objects.
    """
    out = np.zeros((len(candidates), len(objects)))
    if len(candidates) == 0 or len(objects) == 0:
        return out
    centres = np.stack([o.box.center for o in objects])
    reach = max(o.box.half_diagonal for o in objects)
    centre_tree = cKDTree(centres)
    point_trees: Dict[int, cKDTree] = {}
    for c, cand in enumerate(candidates):
        if len(cand.points) == 0:
            continue
        near = centre_tree.query_ball_point(cand.box.center, cand.box.half_diagonal + reach)
        for o in near:
            obj = objects[o]
            if not boxes_intersect(cand.box, obj.box):
                continue
            if o not in point_trees:
                point_trees[o] = cKDTree(obj.points)
            dist, _ = point_trees[o].query(cand.points, k=1, distance_upper_bound=cfg.match_radius_m)
            out[c, o] = np.count_nonzero(np.isfinite(dist)) / len(cand.points)
    return out


# ---------------------------------------------------------------- decision

def appearance_matrix(candidates: Sequence[Candidate], objects: Sequence[StoredObject]) -> np.ndarray:
    """(C, O) cosine similarity of image features. 0 where either side has none."""
    out = np.zeros((len(candidates), len(objects)))
    for c, cand in enumerate(candidates):
        if cand.clip is None:
            continue
        a = np.asarray(cand.clip, dtype=float)
        na = np.linalg.norm(a)
        for o, obj in enumerate(objects):
            if obj.clip is None:
                continue
            b = np.asarray(obj.clip, dtype=float)
            nb = np.linalg.norm(b)
            if na > 0 and nb > 0:
                out[c, o] = float(a @ b) / (na * nb)
    return out


def combined_scores(overlap: np.ndarray, appearance: np.ndarray, cfg: MemoryGraphConfig) -> np.ndarray:
    """(1 + phys_bias) * overlap + (1 - phys_bias) * appearance. Not bounded to [0, 1]."""
    return (1.0 + cfg.phys_bias) * overlap + (1.0 - cfg.phys_bias) * appearance


def match(scores: np.ndarray, cfg: MemoryGraphConfig) -> List[Optional[int]]:
    """For each candidate (row), the object (column) it merges into, or None for
    a new object. A pair is only ever matched if its score is above
    cfg.sim_threshold.

    "greedy": each candidate takes its best object. Two candidates can take the
        same one (upstream).
    "one_to_one": the assignment with the highest total score in which each
        object takes at most one candidate (Hungarian algorithm).
    """
    n_cand, n_obj = scores.shape
    result: List[Optional[int]] = [None] * n_cand
    if n_cand == 0 or n_obj == 0:
        return result
    if cfg.association_mode == "greedy":
        best = scores.argmax(axis=1)
        for c in range(n_cand):
            if scores[c, best[c]] > cfg.sim_threshold:
                result[c] = int(best[c])
        return result
    allowed = scores > cfg.sim_threshold
    # Pairs below the threshold get a weight of 0, so the assignment never
    # prefers them, and any it still picks are discarded below.
    weights = np.where(allowed, scores, 0.0)
    rows, cols = linear_sum_assignment(weights, maximize=True)
    for c, o in zip(rows, cols):
        if allowed[c, o]:
            result[int(c)] = int(o)
    return result


def associate(
    candidates: Sequence[Candidate], objects: Sequence[StoredObject], cfg: MemoryGraphConfig
) -> List[Optional[int]]:
    """S10 end to end: overlap, appearance, combined score, match."""
    scores = combined_scores(
        overlap_matrix(candidates, objects, cfg), appearance_matrix(candidates, objects), cfg
    )
    return match(scores, cfg)
