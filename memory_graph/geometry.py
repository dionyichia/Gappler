"""S7 back-projection, S8 point-cloud cleanup and 3D box, S9 range filter (T6.3e).

This is where pixels become geometry. Upstream uses Open3D for the voxel grid,
DBSCAN and the oriented box (pointcloud.py). Here they are written with numpy and
scipy, which the project already depends on, so no new package is needed.
"""

from __future__ import annotations

from collections import deque
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy.spatial import cKDTree

from memory_graph.config import MemoryGraphConfig
from memory_graph.stage_types import Candidate, Detections, Observation, OrientedBox

Cloud = Tuple[np.ndarray, np.ndarray]   # (points (M, 3), colors (M, 3) in [0, 1])


# ---------------------------------------------------------------- S7

def camera_rays(depth: np.ndarray, K: np.ndarray) -> np.ndarray:
    """(H, W, 3) camera-frame point for every pixel, OpenCV axes.

    x = (u - cx) z / fx, y = (v - cy) z / fy, z = depth. Depth must be distance
    along the optical axis, not along each pixel's ray.
    """
    h, w = depth.shape
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    u, v = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
    z = depth.astype(np.float64)
    return np.stack([(u - cx) * z / fx, (v - cy) * z / fy, z], axis=-1)


def transform_points(T: np.ndarray, points: np.ndarray) -> np.ndarray:
    return points @ T[:3, :3].T + T[:3, 3]


def back_project(obs: Observation, masks: np.ndarray, cfg: MemoryGraphConfig) -> List[Optional[Cloud]]:
    """One world-frame cloud per mask, or None if the mask has fewer than
    cfg.min_points pixels with valid depth (pointcloud.py:138).

    Clouds above cfg.max_points are thinned by taking every k-th point, before the
    pose transform, as upstream does.
    """
    xyz = camera_rays(obs.depth, obs.K)
    valid_depth = obs.depth > 0
    colors_all = obs.rgb.astype(np.float64) / 255.0
    out: List[Optional[Cloud]] = []
    for mask in masks:
        sel = mask & valid_depth
        n = int(np.count_nonzero(sel))
        if n < cfg.min_points:
            out.append(None)
            continue
        pts = xyz[sel]
        cols = colors_all[sel]
        if n > cfg.max_points:
            step = int(np.ceil(n / cfg.max_points))
            pts, cols = pts[::step], cols[::step]
        out.append((transform_points(obs.T_world_cam, pts), cols))
    return out


# ---------------------------------------------------------------- S8

def voxel_downsample(points: np.ndarray, colors: np.ndarray, voxel: float) -> Cloud:
    """One point per occupied voxel: the mean of the points and colours in it."""
    if len(points) == 0:
        return points, colors
    keys = np.floor(points / voxel).astype(np.int64)
    _, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.reshape(-1)
    k = len(counts)
    out_p = np.zeros((k, 3))
    out_c = np.zeros((k, 3))
    np.add.at(out_p, inverse, points)
    np.add.at(out_c, inverse, colors)
    return out_p / counts[:, None], out_c / counts[:, None]


def dbscan_labels(points: np.ndarray, eps: float, min_points: int) -> np.ndarray:
    """DBSCAN cluster id per point, -1 for noise. A point's neighbourhood
    includes itself, as in Open3D's cluster_dbscan."""
    n = len(points)
    labels = np.full(n, -1, dtype=np.int64)
    if n == 0:
        return labels
    neighbours = cKDTree(points).query_ball_point(points, eps)
    core = np.array([len(nb) >= min_points for nb in neighbours], dtype=bool)
    cluster = 0
    for seed in range(n):
        if not core[seed] or labels[seed] != -1:
            continue
        labels[seed] = cluster
        queue = deque([seed])
        while queue:
            p = queue.popleft()
            if not core[p]:
                continue            # border point: joins the cluster, does not grow it
            for q in neighbours[p]:
                if labels[q] == -1:
                    labels[q] = cluster
                    queue.append(q)
        cluster += 1
    return labels


def largest_cluster(points: np.ndarray, colors: np.ndarray, cfg: MemoryGraphConfig) -> Cloud:
    """Keep only the largest DBSCAN cluster. If it has fewer than
    cfg.dbscan_min_cluster_keep points, return the cloud unchanged.

    This assumes one object per mask. It can cut off real parts of thin or
    disconnected objects, chair legs for example.
    """
    labels = dbscan_labels(points, cfg.dbscan_eps_m, cfg.dbscan_min_points)
    clustered = labels[labels >= 0]
    if len(clustered) == 0:
        return points, colors
    biggest = np.bincount(clustered).argmax()
    keep = labels == biggest
    if np.count_nonzero(keep) < cfg.dbscan_min_cluster_keep:
        return points, colors
    return points[keep], colors[keep]


def fit_box(points: np.ndarray) -> OrientedBox:
    """An oriented box from the principal axes of the points.

    Upstream uses Open3D's get_oriented_bounding_box(robust=True), falling back to
    an axis-aligned box (pointcloud.py:124). This uses PCA directly, and falls back
    to axis-aligned when there are too few points for a stable orientation.

    For a cloud with about the same spread in every direction (a cube, a ball)
    the principal axes are arbitrary, so the box can come out up to about 1.7
    times larger per side than the tightest one. It still holds every point, so
    S10's box test only gets less selective, never wrong.
    """
    points = np.asarray(points, dtype=np.float64)
    if len(points) < 4:
        lo, hi = points.min(axis=0), points.max(axis=0)
        return OrientedBox((lo + hi) / 2.0, np.eye(3), hi - lo)
    mean = points.mean(axis=0)
    _, vecs = np.linalg.eigh(np.cov((points - mean).T))
    R = vecs[:, ::-1]                       # largest spread first
    if np.linalg.det(R) < 0:
        R[:, 2] = -R[:, 2]                  # keep it a proper rotation
    local = (points - mean) @ R
    lo, hi = local.min(axis=0), local.max(axis=0)
    return OrientedBox(mean + R @ ((lo + hi) / 2.0), R, hi - lo)


def clean_cloud(points: np.ndarray, colors: np.ndarray, cfg: MemoryGraphConfig) -> Cloud:
    """S8 without the box: voxel downsample, then keep the largest cluster
    (pointcloud.py:366)."""
    points, colors = voxel_downsample(points, colors, cfg.voxel_size_m)
    if cfg.dbscan_remove_noise:
        points, colors = largest_cluster(points, colors, cfg)
    return points, colors


# ---------------------------------------------------------------- S9

def within_range(boxes: Sequence[OrientedBox], camera_position: np.ndarray, max_distance: float) -> np.ndarray:
    """Bool per box: is its centre within max_distance of the camera (map.py:439).
    A full 3D distance, although upstream's comment says 2D."""
    if len(boxes) == 0:
        return np.zeros(0, dtype=bool)
    centres = np.stack([b.center for b in boxes])
    return np.linalg.norm(centres - camera_position, axis=1) <= max_distance


# ---------------------------------------------------------------- S7 to S9

def build_candidates(
    obs: Observation,
    dets: Detections,
    cfg: MemoryGraphConfig,
    features: Optional[np.ndarray] = None,
) -> List[Candidate]:
    """S7 to S9 for one photo. `dets` must carry masks (after S5). `features`, if
    given, holds one S6 vector per detection, in the same order.

    Each candidate records the detection it came from, so nothing has to be kept
    aligned by hand when candidates are dropped.
    """
    if dets.masks is None:
        raise ValueError("build_candidates needs masks; run S4 and S5 first")
    if features is not None and len(features) != len(dets):
        raise ValueError("features must have one row per detection")
    clouds = back_project(obs, dets.masks, cfg)
    cands: List[Candidate] = []
    for i, cloud in enumerate(clouds):
        if cloud is None:
            continue
        pts, cols = clean_cloud(*cloud, cfg)
        if len(pts) == 0:
            continue
        box = fit_box(pts)
        if box.volume < cfg.min_box_volume_m3:
            continue
        cands.append(Candidate(
            points=pts, colors=cols, box=box,
            label=dets.label[i], conf=float(dets.conf[i]), class_id=int(dets.class_id[i]),
            clip=None if features is None else features[i],
            detection_index=i, mask_pixels=int(np.count_nonzero(dets.masks[i])),
        ))
    keep = within_range([c.box for c in cands], obs.camera_position, cfg.max_object_distance_m)
    return [c for c, k in zip(cands, keep) if k]
